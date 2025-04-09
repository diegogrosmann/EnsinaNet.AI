"""
Modelos para configuração e gerenciamento de IAs.

Define os modelos de dados para configurações de IA, arquivos de treinamento,
e gerenciamento de modelos treinados.
"""

import json
import logging
import os
from typing import Any, Optional
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from django.dispatch import receiver

from accounts.models import UserToken
from api.utils.clientsIA import AI_CLIENT_MAPPING, APIClient
from core.types.ai import AIConfig, AIExample, AIExampleDict, AIPrompt, AIResponseDict
from core.types.status import EntityStatus
from core.types.training import TrainingCaptureConfig, TrainingResponse
from django.db.models.signals import post_delete
from core.types.ai_file import AIFileDict, AIFile

logger = logging.getLogger(__name__)
User = get_user_model()


class AIClientGlobalConfiguration(models.Model):
    """Configuração global de cliente de IA.

    Define parâmetros globais para interação com APIs de IA.

    Attributes:
        name (str): Nome amigável da configuração.
        api_client_class (str): Classe do cliente de API a ser utilizada.
        api_url (str): URL base da API (opcional).
        api_key (str): Chave de autenticação da API.
    """
    name = models.CharField(max_length=255)
    api_client_class = models.CharField(max_length=255)
    api_url = models.URLField(blank=True, null=True)
    api_key = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Global - Cliente de IA"
        verbose_name_plural = "Global - Clientes de IA"
        unique_together = (('name', 'api_client_class'),)

    def __str__(self):
        """Retorna a representação em string da configuração global.

        Returns:
            str: Nome da configuração ou classe do cliente.
        """
        if self.name:
            return f"{self.name} ({self.api_client_class})"
        return f"{self.api_client_class}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva a configuração global com validação e registro de log.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.

        Raises:
            ValidationError: Se a validação falhar.
        """
        try:
            self.full_clean()
            super().save(*args, **kwargs)
            logger.info(f"Configuração global de IA salva: {self.api_client_class}")
        except Exception as e:
            logger.error(f"Erro ao salvar configuração global de IA: {e}", exc_info=True)
            raise

    def create_api_client_instance(self) -> APIClient:
        """Cria uma instância do cliente de API configurado globalmente.

        Returns:
            APIClient: Instância do cliente de API.

        Raises:
            ValueError: Se a classe do cliente não for encontrada ou não estiver registrada.
        """
        try:
            client_class = self.get_client_class()
            if not client_class:
                raise ValueError(f"Classe de API não encontrada: {self.api_client_class}")

            return client_class(
                AIConfig(
                    api_key=self.api_key,
                    api_url=self.api_url
                )
            )
        except KeyError:
            logger.error(f"Classe de API não registrada: {self.api_client_class}", exc_info=True)
            raise ValueError(f"Classe de API não registrada: {self.api_client_class}")
        except Exception as e:
            logger.error(f"Erro ao criar cliente de API: {e}", exc_info=True)
            raise

    def get_client_class(self) -> APIClient:
        """Obtém a classe do cliente de API a partir do mapeamento.

        Returns:
            APIClient: Classe do cliente de API ou None se não encontrada.
        """
        client_class = AI_CLIENT_MAPPING.get(self.api_client_class)
        return client_class


class AIClientConfiguration(models.Model):
    """Configuração específica de cliente de IA vinculada a um token.

    Attributes:
        user (User): Usuário associado.
        ai_client (AIClientGlobalConfiguration): Configuração global de IA.
        name (str): Nome personalizado da IA.
        model_name (str): Nome do modelo (opcional).
        configurations (dict): Configurações adicionais em formato JSON.
        training_configurations (dict): Configurações específicas para treinamento.
        use_system_message (bool): Indica se deve usar a mensagem do sistema.
        tokens (ManyToManyField): Tokens associados à configuração.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_configurations')
    ai_client = models.ForeignKey('AIClientGlobalConfiguration', on_delete=models.CASCADE)
    name = models.CharField("Nome da IA (personalizado)", max_length=100)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    configurations = models.JSONField(default=dict, blank=True, null=True)
    training_configurations = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name="Configurações de Treinamento",
        help_text="Configurações específicas para treinamento no formato chave=valor"
    )
    use_system_message = models.BooleanField(
         default=False,
         verbose_name="Usar System Message",
         help_text="Indica se deve utilizar a mensagem do sistema, se suportado pela API."
    )
    tokens = models.ManyToManyField(
        'accounts.UserToken',
        through='AIClientTokenConfig',
        related_name='ai_clients',
        verbose_name="Tokens associados"
    )

    class Meta:
        verbose_name = "Token - Configuração de Cliente de IA"
        verbose_name_plural = "Token - Configurações de Cliente de IA"
        unique_together = ('user', 'name')

    def __str__(self):
        """Retorna a representação em string da configuração do cliente de IA.

        Returns:
            str: Nome da configuração e classe do cliente.
        """
        return f"{self.name} -> {self.ai_client.api_client_class}"

    def create_api_client_instance(self, token: Optional[UserToken] = None) -> APIClient:
        """Cria e retorna uma instância configurada do cliente de API.

        Args:
            token (Optional[UserToken]): Token do usuário para customização (opcional).

        Returns:
            APIClient: Instância configurada do cliente de API.
        """
        try:
            client_class = self.ai_client.get_client_class()

            base_instruction = ''
            prompt = ''
            responses = ''
            if token:
                try:
                    token_config = token.ai_configuration
                    base_instruction = token_config.base_instruction or ''
                    prompt = token_config.prompt or ''
                    responses = token_config.responses or ''
                except Exception as e:
                    logger.warning(f"Erro ao obter configuração de prompt para token {token.id}: {e}", exc_info=True)

            return client_class(AIConfig(
                api_key=self.ai_client.api_key,
                api_url=self.ai_client.api_url,
                model_name=self.model_name,
                configurations=self.configurations,
                use_system_message=self.use_system_message,
                training_configurations=self.training_configurations,
                base_instruction=base_instruction,
                prompt=prompt,
                responses=responses
            ))
        except Exception as e:
            logger.error(f"Erro ao criar instância do cliente de API: {e}", exc_info=True)
            raise


class AIFilesManager(AIClientGlobalConfiguration):
    """Proxy model para gerenciamento de arquivos de IA."""
    class Meta:
        proxy = True
        verbose_name = "Arquivos na IA"
        verbose_name_plural = "Arquivos na IA"


class AIModelsManager(AIClientGlobalConfiguration):
    """Proxy model para gerenciamento de modelos de IA."""
    class Meta:
        proxy = True
        verbose_name = "Gerenciador de Modelos das IAs"
        verbose_name_plural = "Gerenciador de Modelos"


class AIClientTokenConfig(models.Model):
    """Configuração de associação entre Token e configuração de IA.

    Attributes:
        token (UserToken): Token do usuário.
        ai_config (AIClientConfiguration): Configuração de IA associada.
        enabled (bool): Indica se a configuração está habilitada para o token.
        created_at (datetime): Data de criação da associação.
    """
    token = models.ForeignKey('accounts.UserToken', on_delete=models.CASCADE)
    ai_config = models.ForeignKey(AIClientConfiguration, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('token', 'ai_config')
        verbose_name = "Token - IA Habilitada"
        verbose_name_plural = "Token - IAs Habilitadas"

    def __str__(self):
        """Retorna a representação em string da associação de token com IA.

        Returns:
            str: Nome da configuração e status (habilitada/desabilitada).
        """
        status = "habilitada" if self.enabled else "desabilitada"
        return f"{self.ai_config.name} {status} para {self.token.name}"

    def clean(self) -> None:
        """Valida a associação entre token e configuração de IA.

        Raises:
            ValidationError: Se o token não pertencer ao mesmo usuário da configuração.
        """
        super().clean()
        if self.token.user != self.ai_config.user:
            raise ValidationError("O token deve pertencer ao mesmo usuário do AIClientConfiguration.")


class AITrainingFile(models.Model):
    """Arquivo de treinamento vinculado ao usuário.

    Armazena o arquivo de treinamento e informações sobre o upload.

    Attributes:
        user (User): Usuário que carregou o arquivo.
        name (str): Nome do arquivo.
        file_path (str): Caminho interno do arquivo.
        uploaded_at (datetime): Data e hora do upload.
    """
    def _generate_file_path(self) -> str:
        """Gera um caminho único para o arquivo de treinamento.

        Returns:
            str: Caminho gerado para o arquivo.
        """
        unique_id = uuid.uuid4().hex
        filename = f"{unique_id}.json"
        return os.path.join('training_files', filename)

    def get_full_path(self) -> str:
        """Obtém o caminho completo do arquivo de treinamento.

        Returns:
            str: Caminho absoluto do arquivo.
        """
        return os.path.join(settings.MEDIA_ROOT, self.file_path)

    def __init__(self, *args, **kwargs):
        """Inicializa o objeto de arquivo de treinamento.

        Gera um caminho único para o arquivo se não for fornecido.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados, incluindo user, name e file_path.
        """
        super().__init__(*args, **kwargs)
        if not self.file_path:
            self.file_path = self._generate_file_path()

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_files')
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Atributo privado para cache dos dados do arquivo
    _file_data_cache = None

    @property
    def file_data(self) -> AIFileDict:
        """Retorna a coleção de exemplos de treinamento a partir do arquivo.

        Returns:
            AIFileDict: Coleção de dados do arquivo de treinamento.
        """
        if self._file_data_cache is None and self.file_path:
            self._file_data_cache = AIExampleDict.from_file(self.get_full_path())
        return self._file_data_cache

    @file_data.setter
    def file_data(self, value):
        """Define a coleção de dados do arquivo de treinamento.

        Args:
            value: Nova coleção de exemplos de treinamento ou caminho para criação.
        """
        if isinstance(value, AIExampleDict):
            self._file_data_cache = value
        else:
            self._file_data_cache = AIExampleDict.from_file(value)

    def to_data(self) -> 'AIFile':
        """Converte o modelo em uma estrutura de dados para o arquivo de treinamento.

        Returns:
            AITrainingFileData: Objeto com os dados estruturados do arquivo.
        """
        file_size = 0
        full_path = self.get_full_path()
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
        return AIFile(
            id=self.id,
            user_id=self.user.id,
            name=self.name,
            uploaded_at=self.uploaded_at,
            data=self.file_data,
            file_size=file_size,
            example_count=len(self.file_data.items()) if self.file_data else 0
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva o arquivo de treinamento após validação.

        Utiliza um arquivo temporário para garantir a integridade dos dados. Em caso de falha, o arquivo original permanece intacto.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.

        Raises:
            ValidationError: Se o arquivo não contiver exemplos.
        """
        # Valida que o arquivo possui exemplos antes de salvar
        if self._file_data_cache and len(self._file_data_cache.items()) == 0:
            raise ValidationError("Não é possível salvar um arquivo de treinamento sem exemplos.")

        full_path = self.get_full_path()
        temp_path = f"{full_path}.new"
        file_existed = os.path.exists(full_path)

        try:
            # Salva os dados em um arquivo temporário usando o novo método save_file
            if self._file_data_cache:
                self._file_data_cache.save_file(temp_path)
                
            # Salva o modelo no banco de dados
            super().save(*args, **kwargs)
            # Substitui o arquivo original pelo novo, se existir
            if os.path.exists(temp_path):
                if file_existed:
                    os.replace(temp_path, full_path)
                else:
                    os.rename(temp_path, full_path)
        except Exception as e:
            # Remove o arquivo temporário em caso de erro
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            logger.error(f"Erro ao salvar arquivo de treinamento: {e}", exc_info=True)
            raise

    def __str__(self) -> str:
        """Retorna a representação em string do arquivo de treinamento.

        Returns:
            str: Representação com e-mail do usuário e data de upload.
        """
        return f"Arquivo de Treinamento de {self.user.email} carregado em {self.uploaded_at}"

    class Meta:
        unique_together = ('user', 'name')
        verbose_name = "Arquivo de Treinamento"
        verbose_name_plural = "Arquivos de Treinamento"


@receiver(post_delete, sender=AITrainingFile)
def delete_file_on_model_delete(sender: Any, instance: 'AITrainingFile', **kwargs: Any) -> None:
    """Remove o arquivo físico quando o registro do modelo é excluído."""
    if instance.file_path:
        try:
            full_path = instance.get_full_path()
            if os.path.isfile(full_path):
                os.remove(full_path)
        except Exception as e:
            logger.error(f"Erro ao remover arquivo {instance.file_path}: {e}", exc_info=True)


class TokenAIConfiguration(models.Model):
    """Configuração de prompt personalizada para um token de IA.

    Attributes:
        token (UserToken): Token associado.
        base_instruction (str): Instrução base (opcional).
        prompt (str): Prompt personalizado (obrigatório).
        responses (str): Respostas personalizadas (opcional).
    """
    token = models.OneToOneField(UserToken, related_name='ai_configuration', on_delete=models.CASCADE)
    base_instruction = models.TextField(
        blank=True,
        null=True,
        help_text='Instrução base personalizada para este token.'
    )
    prompt = models.TextField(
        blank=False,
        null=False,
        help_text='Prompt específico para cada comparação (obrigatório).'
    )
    responses = models.TextField(
        blank=True,
        null=True,
        help_text='Respostas personalizadas para este token.'
    )

    class Meta:
        verbose_name = "Token - Configuração de IA"
        verbose_name_plural = "Token - Configurações de IA"

    def __str__(self) -> str:
        """Retorna a representação em string da configuração do token.

        Returns:
            str: Informação da configuração associada ao token.
        """
        return f"Configuração de IA para {self.token.name}"

    def clean(self) -> None:
        """Realiza a validação dos dados da configuração.

        Raises:
            ValidationError: Se o campo prompt estiver vazio.
        """
        super().clean()
        if not self.prompt:
            raise ValidationError("O prompt é obrigatório")

    def to_prompt_config(self) -> AIPrompt:
        """Converte a configuração do token para um objeto de configuração de prompt.

        Returns:
            AIPromptConfig: Configuração de prompt estruturada.
        """
        return AIPrompt(
            system_message=self.base_instruction or "",
            user_message=self.prompt,
            response=self.responses or ""
        )


class TrainingCapture(models.Model):
    """Captura de treinamento contendo informações temporárias.

    Attributes:
        token (UserToken): Token associado à captura.
        ai_client_config (AIClientConfiguration): Configuração de IA associada.
        is_active (bool): Indica se a captura está ativa.
        temp_file (str): Caminho para o arquivo temporário.
        create_at (datetime): Data de criação da captura.
        last_activity (datetime): Última atividade registrada.
    """
    def _generate_file_path(self) -> str:
        """Gera um caminho único para o arquivo temporário da captura.

        Returns:
            str: Caminho gerado para o arquivo temporário.
        """
        unique_id = uuid.uuid4().hex
        filename = f"capture_{unique_id}.json"
        return os.path.join('training_captures', filename)

    @classmethod
    def _generate_temp_filename(cls, instance, filename):
        """Gera um caminho único para o arquivo temporário mantendo compatibilidade com migrações existentes.

        Args:
            instance: Instância do modelo TrainingCapture.
            filename (str): Nome original do arquivo enviado.

        Returns:
            str: Caminho de destino para o arquivo temporário.
        """
        if instance and hasattr(instance, 'token') and instance.token:
            token_id = instance.token.id
        else:
            token_id = "unknown"
        unique_id = uuid.uuid4().hex
        filename = f"capture_{token_id}_{unique_id}.json"
        return os.path.join('training_captures', filename)

    def get_full_path(self) -> str:
        """Obtém o caminho completo do arquivo temporário.

        Returns:
            str: Caminho absoluto do arquivo temporário.
        """
        return os.path.join(settings.MEDIA_ROOT, self.temp_file)

    token = models.ForeignKey(UserToken, related_name='training_captures', on_delete=models.CASCADE)
    ai_client_config = models.ForeignKey('AIClientConfiguration', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)
    temp_file = models.CharField(max_length=255, editable=False)
    create_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    # Atributo privado para cache dos dados do arquivo temporário
    _file_data_cache = None

    def __init__(self, *args, **kwargs):
        """Inicializa a captura de treinamento.

        Gera um caminho único para o arquivo temporário se não for fornecido.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        super().__init__(*args, **kwargs)
        if not self.temp_file:
            self.temp_file = self._generate_file_path()

    @property
    def file_data(self) -> AIExampleDict:
        """Retorna a coleção de exemplos de treinamento a partir do arquivo temporário.

        Returns:
            AIExampleDict: Coleção de exemplos de treinamento.
        """
        if self._file_data_cache is None and self.temp_file:
            full_path = self.get_full_path()
            if os.path.exists(full_path):
                self._file_data_cache = AIExampleDict.from_file(full_path)
            else:
                self._file_data_cache = AIExampleDict()  # Retornar AIExampleDict vazio, não AIFileDict
        return self._file_data_cache

    @file_data.setter
    def file_data(self, value):
        """Define a coleção de exemplos de treinamento.

        Args:
            value: Nova coleção de exemplos ou caminho para criação da coleção.
        """
        if isinstance(value, AIExampleDict):
            self._file_data_cache = value
        else:
            self._file_data_cache = AIExampleDict.from_file(value)

    def add_example(self, example: AIExample) -> None:
        """Adiciona um exemplo de treinamento à captura.
        
        Args:
            example: O exemplo de treinamento a ser adicionado.
        """
        if self.file_data is None:
            self.file_data = AIExampleDict()
        
        example_id = str(uuid.uuid4())  # Gerar um ID único para o exemplo
        self.file_data.put_item(example_id, example)
        self.save()  # Salvar para persistir as mudanças no arquivo

    def to_data(self) -> 'TrainingCaptureConfig':
        """Converte o modelo de captura em uma estrutura de dados.

        Returns:
            AITrainingCaptureConfig: Objeto estruturado com os dados da captura.
        """
        return TrainingCaptureConfig(
            id=self.id,
            token_id=self.token.id,
            ai_client_config_id=self.ai_client_config.id,
            is_active=self.is_active,
            data=self.file_data,
            create_at=self.create_at,
            last_activity=self.last_activity
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva a captura de treinamento após validação.

        Utiliza um arquivo temporário para garantir a integridade dos dados.
        Em caso de erro, o arquivo temporário é removido.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
            
        Raises:
            TypeError: Se o cache de dados não for do tipo AIExampleDict.
        """
        full_path = self.get_full_path()
        temp_path = f"{full_path}.new"
        file_existed = os.path.exists(full_path)

        try:
            # Garantir que o diretório exista
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Inicializar cache vazio se for None
            if self._file_data_cache is None:
                self._file_data_cache = AIExampleDict()
                
            # Verificar se o cache é do tipo esperado
            if not isinstance(self._file_data_cache, AIExampleDict):
                raise TypeError(f"O cache de dados deve ser do tipo AIExampleDict, não {type(self._file_data_cache).__name__}")
            
            # Sempre salvar o arquivo, mesmo que esteja vazio
            self._file_data_cache.save_file(temp_path)
                
            # Salva o modelo no banco de dados
            super().save(*args, **kwargs)
            # Substitui ou move o arquivo temporário para o caminho final
            if os.path.exists(temp_path):
                if file_existed:
                    os.replace(temp_path, full_path)
                else:
                    os.rename(temp_path, full_path)
        except Exception as e:
            # Remove o arquivo temporário em caso de erro
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            logger.error(f"Erro ao salvar captura de treinamento: {e}", exc_info=True)
            raise

    class Meta:
        unique_together = ('token',)
        verbose_name = "Captura de Treinamento"
        verbose_name_plural = "Capturas de Treinamento"

    def __str__(self) -> str:
        """Retorna a representação em string da captura de treinamento.

        Returns:
            str: Status da captura e informações do token e configuração de IA.
        """
        status_str = "Ativa" if self.is_active else "Inativa"
        return f"Captura {status_str} para {self.ai_client_config} do Token {self.token.name}"


@receiver(post_delete, sender=TrainingCapture)
def delete_temp_file_on_delete(sender: Any, instance: 'TrainingCapture', **kwargs: Any) -> None:
    """Remove o arquivo temporário quando a captura é deletada."""
    if instance.temp_file:
        full_path = instance.get_full_path()
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                logger.debug(f"Arquivo temporário deletado: {full_path}")
            except Exception as e:
                logger.error(f"Erro ao deletar arquivo temporário: {e}", exc_info=True)


class DoclingConfiguration(models.Model):
    """Configuração específica para o Docling.

    Attributes:
        do_ocr (bool): Indica se deve executar OCR.
        do_table_structure (bool): Indica extração de estrutura de tabela.
        do_cell_matching (bool): Indica se deve ativar a correspondência de células.
        accelerator_device (str): Dispositivo de aceleração a ser utilizado.
        custom_options (dict): Opções customizadas adicionais (opcional).
    """
    do_ocr = models.BooleanField(default=False, verbose_name="Executar OCR")
    do_table_structure = models.BooleanField(default=False, verbose_name="Extrair Estrutura de Tabela")
    do_cell_matching = models.BooleanField(default=False, verbose_name="Ativar Correspondência de Células")

    ACCELERATOR_CHOICES = [
        ("auto", "Auto"),
        ("cpu", "CPU"),
        ("cuda", "CUDA"),
        ("mps", "MPS"),
    ]
    accelerator_device = models.CharField(
        max_length=10,
        choices=ACCELERATOR_CHOICES,
        default="auto",
        verbose_name="Dispositivo de Aceleração"
    )

    custom_options = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Opções Customizadas",
        help_text="Insira opções adicionais em formato JSON (por exemplo, {'images_scale': 1.2})."
    )

    class Meta:
        verbose_name = "Configuração Docling"
        verbose_name_plural = "Configurações Docling"

    def __str__(self) -> str:
        """Retorna a representação textual da configuração Docling.

        Returns:
            str: Descrição da configuração.
        """
        return "Configuração Docling"


class AITraining(models.Model):
    """Armazena informações sobre treinamentos de IA.

    Attributes:
        ai_config (AIClientConfiguration): Configuração da IA em treinamento.
        file (AITrainingFile): Arquivo utilizado no treinamento.
        job_id (str): ID do job de treinamento na API.
        status (str): Status atual do treinamento.
        model_name (str): Nome do modelo gerado (se concluído).
        error (str): Mensagem de erro (se ocorreu falha).
        created_at (datetime): Data de início do treinamento.
        updated_at (datetime): Data da última atualização.
        progress (float): Progresso do treinamento.
    """
    ai_config = models.ForeignKey('AIClientConfiguration', on_delete=models.CASCADE)
    file = models.ForeignKey('AITrainingFile', on_delete=models.SET_NULL, null=True)
    job_id = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=[(status.value, status.name) for status in EntityStatus],
        default=EntityStatus.NOT_STARTED.value
    )
    model_name = models.CharField(max_length=255, null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    progress = models.FloatField(default=0)

    class Meta:
        verbose_name = "Treinamento de IA"
        verbose_name_plural = "Treinamentos de IA"

    def __str__(self) -> str:
        """Retorna a representação em string do treinamento.

        Returns:
            str: Representação contendo o job ID e o status.
        """
        status_display = dict((status.value, status.name) for status in EntityStatus).get(self.status, self.status)
        return f"Treinamento {self.job_id} - {status_display}"

    def get_global_client(self) -> AIClientGlobalConfiguration:
        """Retorna a configuração global do cliente de IA.

        Returns:
            AIClientGlobalConfiguration: Configuração global associada.
        """
        return self.ai_config.ai_client

    def cancel_training(self) -> bool:
        """Cancela um treinamento em andamento.

        Returns:
            bool: True se o cancelamento foi bem-sucedido, False caso contrário.
        """
        try:
            if self.status != 'in_progress':
                return False

            client = self.ai_config.create_api_client_instance()
            if not client.can_train:
                return False

            result = client.cancel_training(self.job_id)
            if result.success:
                self.status = 'cancelled'
                self.save()
            return result.success
        except Exception as e:
            logger.error(f"Erro ao cancelar treinamento {self.job_id}: {e}", exc_info=True)
            return False

    def get_training_data(self) -> TrainingResponse:
        """Obtém os dados atualizados do treinamento.

        Returns:
            TrainingResponse: Objeto contendo os dados do status do treinamento.
        """
        try:
            client = self.ai_config.create_api_client_instance()
            if not client.can_train:
                return TrainingResponse(
                    job_id=self.job_id,
                    status=EntityStatus.FAILED,
                    error="Cliente não suporta treinamento"
                )
            return client.get_training_status(self.job_id)
        except Exception as e:
            logger.error(f"Erro ao obter status de treinamento {self.job_id}: {e}", exc_info=True)
            return TrainingResponse(
                job_id=self.job_id,
                status=EntityStatus.FAILED,
                error=str(e)
            )

    def update_training_status(self) -> bool:
        """Atualiza e salva o status do treinamento com base nos dados da API.

        Este método consulta o status atual do treinamento na API e atualiza 
        os campos do objeto AITraining de acordo.

        Returns:
            bool: True se o status foi atualizado com sucesso, False caso contrário.
        """
        try:
            training_response = self.get_training_data()
            
            # Atualiza os campos do objeto com base no status retornado
            self.status = training_response.status.value
            self.progress = training_response.progress
            
            # Se o treinamento foi concluído com sucesso, armazena o nome do modelo
            if training_response.status == EntityStatus.COMPLETED:
                self.model_name = training_response.model_name
            
            # Se o treinamento falhou, armazena o erro
            if training_response.status == EntityStatus.FAILED:
                self.error = training_response.error
            
            # Salva as alterações no banco de dados
            self.save()
            logger.info(f"Status do treinamento {self.job_id} atualizado: {self.status}, progresso: {self.progress}")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar status do treinamento {self.job_id}: {e}", exc_info=True)
            return False


@receiver(post_delete, sender=AITraining)
def delete_model_on_training_delete(sender: Any, instance: 'AITraining', **kwargs: Any) -> None:
    """Remove o modelo treinado quando o registro de treinamento é excluído."""
    if instance.model_name and instance.status == 'completed':
        try:
            client = instance.ai_config.create_api_client_instance()
            client.delete_trained_model(instance.model_name)
        except Exception as e:
            logger.error(f"Erro ao excluir modelo {instance.model_name}: {e}", exc_info=True)
