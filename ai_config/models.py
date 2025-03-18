"""Modelos para configuração e gerenciamento de IAs.

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
from core.types import (
    AIConfig,
    AIPromptConfig,
    AITrainingStatus,
    AITrainingResponse,
    AITrainingExampleCollection,
)
from core.types.training import AITrainingCaptureConfig, AITrainingFileData

from .storage import OverwriteStorage
from django.db.models.signals import post_delete

logger = logging.getLogger(__name__)
User = get_user_model()

class AIClientGlobalConfiguration(models.Model):
    """Configuração global de cliente de IA.
    
    Define parâmetros globais para interação com APIs de IA.
    
    Attributes:
        name: Nome amigável da configuração.
        api_client_class: Classe do cliente de API a ser usada.
        api_url: URL base da API (opcional).
        api_key: Chave de autenticação da API.
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
        """Retorna a representação em string do objeto.

        Returns:
            str: Representação com base no nome ou na classe da API cliente.
        """
        if self.name:
            return f"{self.name} ({self.api_client_class})"
        return f"{self.api_client_class}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva a configuração com validação e log.
        
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
            logger.error(f"Erro ao salvar configuração global de IA: {e}")
            raise

    def create_api_client_instance(self) -> APIClient:
        """Cria uma instância do cliente de API.
        
        Args:
            **kwargs: Argumentos adicionais para o cliente.
            
        Returns:
            APIClient: Instância do cliente de API.
            
        Raises:
            ValueError: Se a classe do cliente não existir.
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
            logger.error(f"Classe de API não registrada: {self.api_client_class}")
            raise ValueError(f"Classe de API não registrada: {self.api_client_class}")
        except Exception as e:
            logger.error(f"Erro ao criar cliente de API: {e}")
            raise

    def get_client_class(self) -> APIClient:
        client_class = AI_CLIENT_MAPPING.get(self.api_client_class)
        return client_class

class AIClientConfiguration(models.Model):
    """Configuração específica vinculada a um token e um cliente global de IA.

    Attributes:
        ai_client: Referência à configuração global de IA.
        name (str): Nome personalizado da IA.
        model_name (str): Nome do modelo (opcional).
        configurations (dict): Configurações adicionais em JSON.
        training_configurations (dict): Configurações específicas para treinamento em JSON.
        use_system_message (bool): Indica se deve usar a mensagem do sistema.
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
        """Representação textual da configuração do cliente de IA.

        Returns:
            str: Informação sobre o token e a classe de IA.
        """
        return f"{self.name} -> {self.ai_client.api_client_class}"

    def create_api_client_instance(self, token: Optional[UserToken] = None) -> APIClient:
        """Retorna uma instância configurada do cliente de IA.
        
        Args:
            token: Token opcional do usuário para customização

        Returns:
            APIClient: Instância configurada do cliente
        """
        try:
            client_class = self.ai_client.get_client_class()
            
            prompt_config = None
            if token:
                try:
                    token_config = token.ai_configuration 
                    prompt_config = token_config.to_prompt_config()  # Usar o método mais específico
                except Exception as e:
                    logger.warning(f"Erro ao obter configuração de prompt para token {token.id}: {e}")

            return client_class(AIConfig(
                api_key=self.ai_client.api_key,
                api_url=self.ai_client.api_url,
                model_name=self.model_name,
                configurations=self.configurations,
                use_system_message=self.use_system_message,
                training_configurations=self.training_configurations,
                prompt_config=prompt_config
            ))
            
        except Exception as e:
            logger.error(f"Erro ao criar cliente de API: {e}")
            raise

class AIFilesManager(AIClientGlobalConfiguration):
    """Proxy model para gerenciar arquivos de IA."""
    
    class Meta:
        proxy = True
        verbose_name = "Arquivos na IA"
        verbose_name_plural = "Arquivos na IA"

class AIModelsManager(AIClientGlobalConfiguration):
    """Proxy model para gerenciar modelos."""
    
    class Meta:
        proxy = True
        verbose_name = "Gerenciador de Modelos das IAs"
        verbose_name_plural = "Gerenciador de Modelos"

class AIClientTokenConfig(models.Model):
    """Configuração de associação entre Token e IA.
    
    Attributes:
        token: Token do usuário
        ai_config: Configuração da IA
        enabled (bool): Indica se está habilitada para este token
        created_at: Data de criação da associação
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
        status = "habilitada" if self.enabled else "desabilitada"
        return f"{self.ai_config.name} {status} para {self.token.name}"

    def clean(self) -> None:
        super().clean()
        if self.token.user != self.ai_config.user:
            raise ValidationError(
                "O token deve pertencer ao mesmo usuário do AIClientConfiguration."
            )

class AITrainingFile(models.Model):
    """Arquivo de treinamento vinculado ao usuário.

    Armazena o arquivo e as informações de upload.

    Attributes:
        user: Usuário que carregou o arquivo.
        name (str): Nome do arquivo.
        file_path: Caminho do arquivo gerado internamente.
        uploaded_at: Data e hora do upload.
        file_data: Coleção de arquivos de treinamento (não persistido no BD).
    """
    def _generate_file_path(self) -> str:
        """Gera um caminho único para o arquivo."""
        unique_id = uuid.uuid4().hex
        filename = f"{unique_id}.json"
        return os.path.join('training_files', filename)
    
    def get_full_path(self) -> str:
        """Retorna o caminho completo do arquivo."""
        return os.path.join(settings.MEDIA_ROOT, self.file_path)
        
    def __init__(self, *args, **kwargs):
        """Inicializa o arquivo de treinamento.
        
        Gera um caminho de arquivo único se não for fornecido.
        
        Args:
            *args: Argumentos posicionais para a classe pai.
            **kwargs: Argumentos nomeados, incluindo user, name e file_path.
        """
        super().__init__(*args, **kwargs)

        if not self.file_path:
            self.file_path = self._generate_file_path()

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_files')
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Atributo privado para cache do file_data
    _file_data_cache = None
    
    @property
    def file_data(self) -> AITrainingExampleCollection:
        """Retorna uma coleção de arquivos de treinamento baseada no arquivo.
        
        Returns:
            AITrainingExampleCollection: Coleção de arquivos de treinamento
        """
        if self._file_data_cache is None and self.file_path:
            self._file_data_cache = AITrainingExampleCollection.create(self.get_full_path())
        return self._file_data_cache
    
    @file_data.setter
    def file_data(self, value):
        """Define a coleção de arquivos de treinamento.
        
        Args:
            value: Nova coleção de arquivos de treinamento
        """
        if isinstance(value, AITrainingExampleCollection):
            self._file_data_cache = value
        else:
            self._file_data_cache = AITrainingExampleCollection.create(value)

    def to_data(self) -> 'AITrainingFileData':
        """Converte o modelo em uma estrutura de dados AITrainingFileData.
        
        Esta função transfere os dados do modelo para um objeto de tipo de dados,
        possibilitando sua utilização em contextos onde a estrutura do Django
        não está disponível ou não é adequada.
        
        Returns:
            AITrainingFileData: Objeto com os dados estruturados do arquivo
        """        
        # Obtém o tamanho do arquivo se ele existir
        file_size = 0
        full_path = self.get_full_path()
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            
        return AITrainingFileData(
            id=self.id,
            user_id=self.user.id,
            name=self.name,
            uploaded_at=self.uploaded_at,
            file=self.file_data,
            file_size=file_size,
            example_count=len(self.file_data.examples) if self.file_data else 0
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva o arquivo após validação.
        
        Usa um arquivo temporário para garantir a integridade dos dados.
        Se a operação falhar, o arquivo original permanece intacto.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
            
        Raises:
            ValidationError: Se a validação falhar.
        """
        # Verifica se há exemplos antes de permitir o salvamento
        if self._file_data_cache and len(self._file_data_cache.examples) == 0:
            raise ValidationError("Não é possível salvar um arquivo de treinamento sem exemplos.")
        
        # Caminho para o arquivo temporário
        full_path = self.get_full_path()
        temp_path = f"{full_path}.new"
        file_existed = os.path.exists(full_path)
        
        try:
            # Salvar primeiro em um arquivo temporário
            if self._file_data_cache:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._file_data_cache.to_dict(), f, indent=2)
            
            # Salvar o modelo no banco de dados
            super().save(*args, **kwargs)
            
            # Se chegou até aqui, a operação foi bem-sucedida
            # Agora podemos substituir o arquivo original pelo novo
            if os.path.exists(temp_path):
                if file_existed:
                    # Se o arquivo já existia, substitui-o pelo novo
                    os.replace(temp_path, full_path)
                else:
                    # Se é um arquivo novo, apenas mover para o lugar correto
                    os.rename(temp_path, full_path)
                
        except Exception as e:
            # Em caso de erro, remove apenas o arquivo temporário
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass  # Ignora erros na limpeza do arquivo temporário
            
            logger.error(f"Erro ao salvar arquivo de treinamento: {e}")
            raise  # Re-lança a exceção para tratamento superior

    def __str__(self) -> str:
        """Retorna a representação em string do arquivo de treinamento.

        Returns:
            str: String com o e-mail do usuário e data de upload.
        """
        return f"Arquivo de Treinamento de {self.user.email} carregado em {self.uploaded_at}"

    class Meta:
        unique_together = ('user', 'name')  # Garante nomes únicos para cada usuário
        verbose_name = "Arquivo de Treinamento"
        verbose_name_plural = "Arquivos de Treinamento"

@receiver(post_delete, sender=AITrainingFile)
def delete_file_on_model_delete(sender: Any, instance: 'AITrainingFile', **kwargs: Any) -> None:
    """Remove o arquivo físico quando o modelo é excluído."""
    if instance.file_path:
        try:
            full_path = instance.get_full_path()
            if os.path.isfile(full_path):
                os.remove(full_path)
        except Exception as e:
            logger.error(f"Erro ao remover arquivo {instance.file_path}: {e}")

class TokenAIConfiguration(models.Model):
    """Configuração de prompt para um token de IA.

    Attributes:
        token: Token associado.
        base_instruction (str): Instrução base (opcional).
        prompt (str): Prompt personalizado (obrigatório).
        responses (str): Respostas personalizadas (obrigatório).
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
        """Representação em string da configuração do token."""
        return f"Configuração de IA para {self.token.name}"

    def clean(self) -> None:
        """Valida os dados do modelo."""
        super().clean()
        if not self.prompt:
            raise ValidationError("O prompt é obrigatório")

    def to_prompt_config(self) -> AIPromptConfig:
        """Converte a configuração para um objeto de configuração de prompt.
        
        Returns:
            AIPromptConfig: Configuração de prompt estruturada
        """
        return AIPromptConfig(
            system_message=self.base_instruction or "",
            user_message=self.prompt,
            response=self.responses or ""
        )

class TrainingCapture(models.Model):
    """Captura de treinamento contendo informações temporárias.

    Attributes:
        token: Token associado.
        ai_client_config: Configuração de IA.
        is_active (bool): Indica se a captura está ativa.
        temp_file: Arquivo temporário (opcional).
        create_at: Data de criação.
        last_activity: Última atividade registrada.
    """
    
    def _generate_file_path(self) -> str:
        """Gera um caminho único para o arquivo temporário."""
        unique_id = uuid.uuid4().hex
        filename = f"capture_{unique_id}.json"
        return os.path.join('training_captures', filename)
    
    @classmethod
    def _generate_temp_filename(cls, instance, filename):
        """Gera um caminho único para o arquivo temporário.
        
        Este método é usado por migrações existentes e deve ser mantido
        para compatibilidade com o banco de dados.
        
        Args:
            instance: Instância do modelo TrainingCapture.
            filename: Nome original do arquivo enviado.
            
        Returns:
            str: Caminho de destino para o arquivo.
        """
        if instance and hasattr(instance, 'token') and instance.token:
            token_id = instance.token.id
        else:
            token_id = "unknown"
            
        unique_id = uuid.uuid4().hex
        filename = f"capture_{token_id}_{unique_id}.json"
        return os.path.join('training_captures', filename)
    
    def get_full_path(self) -> str:
        """Retorna o caminho completo do arquivo temporário."""
        return os.path.join(settings.MEDIA_ROOT, self.temp_file)

    token = models.ForeignKey(UserToken, related_name='training_captures', on_delete=models.CASCADE)
    ai_client_config = models.ForeignKey('AIClientConfiguration', on_delete=models.CASCADE) 
    is_active = models.BooleanField(default=False)
    temp_file = models.CharField(max_length=255, editable=False)
    create_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    # Atributo privado para cache do file_data
    _file_data_cache = None
    
    def __init__(self, *args, **kwargs):
        """Inicializa a captura de treinamento.
        
        Gera um caminho de arquivo único se não for fornecido.
        
        Args:
            *args: Argumentos posicionais para a classe pai.
            **kwargs: Argumentos nomeados.
        """
        super().__init__(*args, **kwargs)

        if not self.temp_file:
            self.temp_file = self._generate_file_path()
    
    @property
    def file_data(self) -> AITrainingExampleCollection:
        """Retorna uma coleção de exemplos de treinamento baseada no arquivo temporário.
        
        Returns:
            AITrainingExampleCollection: Coleção de exemplos de treinamento
        """
        if self._file_data_cache is None and self.temp_file:
            full_path = self.get_full_path()
            if os.path.exists(full_path):
                self._file_data_cache = AITrainingExampleCollection.create(full_path)
            else:
                self._file_data_cache = AITrainingExampleCollection()
        return self._file_data_cache
    
    @file_data.setter
    def file_data(self, value):
        """Define a coleção de exemplos de treinamento.
        
        Args:
            value: Nova coleção de exemplos de treinamento
        """
        if isinstance(value, AITrainingExampleCollection):
            self._file_data_cache = value
        else:
            self._file_data_cache = AITrainingExampleCollection.create(value)

    def to_data(self) -> 'AITrainingCaptureConfig':
        """Converte o modelo em uma estrutura de dados AITrainingCaptureConfig.
        
        Esta função transfere os dados do modelo para um objeto de tipo de dados,
        possibilitando sua utilização em contextos onde a estrutura do Django
        não está disponível ou não é adequada.
        
        Returns:
            AITrainingCaptureConfig: Objeto com os dados estruturados da captura
        """        
        return AITrainingCaptureConfig(
            id=self.id,
            token_id=self.token.id,
            ai_client_config_id=self.ai_client_config.id,
            is_active=self.is_active,
            file=self.file_data,
            create_at=self.create_at,
            last_activity=self.last_activity
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva a captura após validação.
        
        Usa um arquivo temporário para garantir a integridade dos dados.
        Se a operação falhar, o arquivo original permanece intacto.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        # Caminho para o arquivo temporário
        full_path = self.get_full_path()
        temp_path = f"{full_path}.new"
        file_existed = os.path.exists(full_path)
        
        try:
            # Salvar primeiro em um arquivo temporário
            if self._file_data_cache:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._file_data_cache.to_dict(), f, indent=2)
            
            # Salvar o modelo no banco de dados
            super().save(*args, **kwargs)
            
            # Se chegou até aqui, a operação foi bem-sucedida
            # Agora podemos substituir o arquivo original pelo novo
            if os.path.exists(temp_path):
                if file_existed:
                    # Se o arquivo já existia, substitui-o pelo novo
                    os.replace(temp_path, full_path)
                else:
                    # Se é um arquivo novo, apenas mover para o lugar correto
                    os.rename(temp_path, full_path)
                
        except Exception as e:
            # Em caso de erro, remove apenas o arquivo temporário
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass  # Ignora erros na limpeza do arquivo temporário
            
            logger.error(f"Erro ao salvar captura de treinamento: {e}")
            raise  # Re-lança a exceção para tratamento superior

    class Meta:
        unique_together = ('token',)
        verbose_name = "Captura de Treinamento"
        verbose_name_plural = "Capturas de Treinamento"

    def __str__(self) -> str:
        """Retorna a representação em string da captura.

        Returns:
            str: Status e informações do token e da IA.
        """
        status = "Ativa" if self.is_active else "Inativa"
        return f"Captura {status} para {self.ai_client_config} do Token {self.token.name}"

@receiver(post_delete, sender=TrainingCapture)
def delete_temp_file_on_delete(sender: Any, instance: 'TrainingCapture', **kwargs: Any) -> None:
    """Remove o arquivo temporário quando a captura for deletada."""
    if instance.temp_file:
        full_path = instance.get_full_path()
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
                logger.debug(f"Arquivo temporário deletado: {full_path}")
            except Exception as e:
                logger.error(f"Erro ao deletar arquivo temporário: {e}")

class DoclingConfiguration(models.Model):
    """Configuração específica para o Docling.

    Attributes:
        do_ocr (bool): Indica se deve executar OCR.
        do_table_structure (bool): Indica extração de estrutura de tabela.
        do_cell_matching (bool): Indica ativação de correspondência de células.
        accelerator_device (str): Dispositivo de aceleração.
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
            str: Texto descritivo da configuração.
        """
        return "Configuração Docling"

class AITraining(models.Model):
    """Armazena informações sobre treinamentos de IAs.

    Attributes:
        ai_config: Configuração da IA sendo treinada
        file: Arquivo usado no treinamento
        job_id: ID do job de treinamento na API
        status: Status atual do treinamento
        model_name: Nome do modelo gerado (se concluído)
        error: Mensagem de erro (se falhou)
        created_at: Data de início
        updated_at: Última atualização
    """
    STATUS_CHOICES = [
        ('not_started', 'Não Iniciado'),
        ('in_progress', 'Em Andamento'),
        ('completed', 'Concluído'),
        ('failed', 'Falhou')
    ]
    
    ai_config = models.ForeignKey('AIClientConfiguration', on_delete=models.CASCADE)
    file = models.ForeignKey('AITrainingFile', on_delete=models.SET_NULL, null=True)
    job_id = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES,
        default='not_started'
    )
    model_name = models.CharField(max_length=255, null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    progress = models.FloatField(default=0)  # Adicionar este campo

    class Meta:
        verbose_name = "Treinamento de IA"
        verbose_name_plural = "Treinamentos de IA"

    def __str__(self) -> str:
        """Representação em string do treinamento."""
        status_display = dict(self.STATUS_CHOICES).get(self.status, self.status)
        return f"Treinamento {self.job_id} - {status_display}"

    def get_global_client(self) -> AIClientGlobalConfiguration:
        """Retorna a configuração global do cliente."""
        return self.ai_config.ai_client

    def cancel_training(self) -> bool:
        """Cancela um treinamento em andamento."""
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
            logger.error(f"Erro ao cancelar treinamento {self.job_id}: {e}")
            return False

    def get_training_data(self) -> AITrainingResponse:
        """Obtém os dados atualizados do treinamento."""
        try:
            client = self.ai_config.create_api_client_instance()
            if not client.can_train:
                return AITrainingResponse(
                    job_id=self.job_id,
                    status=AITrainingStatus.FAILED,
                    error="Cliente não suporta treinamento"
                )
            return client.get_training_status(self.job_id)
        except Exception as e:
            logger.error(f"Erro ao obter status de treinamento {self.job_id}: {e}")
            return AITrainingResponse(
                job_id=self.job_id,
                status=AITrainingStatus.FAILED,
                error=str(e)
            )

@receiver(post_delete, sender=AITraining)
def delete_model_on_training_delete(sender: Any, instance: 'AITraining', **kwargs: Any) -> None:
    """Remove o modelo treinado quando o registro de treinamento é excluído."""
    if instance.model_name and instance.status == 'completed':
        try:
            client = instance.ai_config.create_api_client_instance()
            client.delete_trained_model(instance.model_name)
        except Exception as e:
            logger.error(f"Erro ao excluir modelo {instance.model_name}: {e}")
