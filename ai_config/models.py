"""Módulo de modelos da aplicação de configuração de IA.

Contém definições de modelos para armazenar configurações, treinamento e arquivos relacionados à IA.
"""

import logging
import uuid
import os

from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_delete
from django.contrib.auth import get_user_model
from django.conf import settings
from jsonschema import ValidationError

from accounts.models import UserToken
from api.constants import AIClientConfig
from api.utils.clientsIA import AI_CLIENT_MAPPING, APIClient

from .storage import OverwriteStorage

# Configuração do logger
logger = logging.getLogger(__name__)

User = get_user_model()

class AIClientGlobalConfiguration(models.Model):
    """Configuração global do cliente de IA.

    Attributes:
        name (str): Nome do cliente.
        api_client_class (str): Classe da API cliente.
        api_url (str): URL da API (opcional).
        api_key (str): Chave de acesso à API.

    NOTA:
        A api_client_class relaciona-se com a classe APIClient do módulo api_client.
        Como a APIClient é uma classe abstrata, e não é persistida no BD, a api_client_class é uma string.
        A relação entre a api_client_class e a classe APIClient um para muitos.
        A relação indica que uma API pode estar associada a múltiplas configurações 
        globais de cliente, mas cada configuração global pertence a apenas uma API.
        Essa relação deve ser exibida no Diagrama de Classes.
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
            return f"({self.api_client_class}) {self.name}"
        return f"Cliente de IA para {self.api_client_class}"

    def to_dict(self):
        """Converte a configuração global em um dicionário.

        Returns:
            dict: Dicionário com os atributos da configuração global.
        """
        return {
            'id': self.id,
            'name': self.name,
            'api_client_class': self.api_client_class,
            'api_key': self.api_key,
            'api_url': self.api_url,
        }

    def __create_api_client_instance(self) -> APIClient:
        """
        Retorna uma instância do cliente de API de IA.
        Este método cria e configura uma instância de cliente de API baseado na
        classe de cliente especificada em `api_client_class`.
        Returns:
            APIClient: Uma instância configurada do cliente de API de IA.
        Raises:
            ValueError: Se a classe de cliente especificada não for encontrada no mapeamento.
        """
        client_class = AI_CLIENT_MAPPING.get(self.api_client_class)
        if not client_class:
            raise ValueError(f"Cliente não encontrado: {self.api_client_class}")
        
        # Nova estrutura de configuração usando to_dict()
        client_config = AIClientConfig(
            ai_global_config=self.to_dict(),
            ai_client_config={},
            prompt_config={}  # Dicionário vazio em vez de AIPromptConfig()
        )
        return client_class(client_config)

    def get_client_name(self):
        client_class = AI_CLIENT_MAPPING.get(self.api_client_class)
        return client_class.name
    
    def get_client_can_train(self):
        client_class = AI_CLIENT_MAPPING.get(self.api_client_class)
        return client_class.can_train
    
    def get_client_supports_system_message(self):
        client_class = AI_CLIENT_MAPPING.get(self.api_client_class)
        return client_class.supports_system_message

    def list_files(self) -> list:
        """Lista todos os arquivos disponíveis.

        Returns:
            list: Lista de arquivos.

        Raises:
            Exception: Se ocorrer erro ao listar os arquivos.
        """
        try:
            client = self.__create_api_client_instance()
            if not client.can_train:
                return []
            return client.list_files()
        except Exception as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            raise

    def list_trained_models(self) -> list:
        """Lista todos os modelos treinados disponíveis.

        Returns:
            list: Lista de modelos treinados.

        Raises:
            Exception: Se ocorrer erro ao listar os modelos.
        """
        try:
            client = self.__create_api_client_instance()
            if not client.can_train:
                return []
            return client.list_trained_models()
        except Exception as e:
            logger.error(f"Erro ao listar modelos treinados: {e}")
            raise

    def delete_training_file(self, file_id: str) -> bool:
        """Remove um arquivo de treinamento.

        Args:
            file_id (str): ID do arquivo a ser removido.

        Returns:
            bool: True se removido com sucesso.

        Raises:
            Exception: Se ocorrer erro ao remover o arquivo.
        """
        try:
            client = self.create_api_client_instance()
            if not client.can_train:
                return False
            return client.delete_training_file(file_id)
        except Exception as e:
            logger.error(f"Erro ao remover arquivo de treinamento: {e}")
            raise

    def delete_trained_model(self, model_name: str) -> bool:
        """Remove um modelo treinado.

        Args:
            model_name (str): Nome do modelo a ser removido.

        Returns:
            bool: True se removido com sucesso.

        Raises:
            Exception: Se ocorrer erro ao remover o modelo.
        """
        try:
            client = self.__create_api_client_instance()
            if not client.can_train:
                return False
            return client.delete_trained_model(model_name)
        except Exception as e:
            logger.error(f"Erro ao remover modelo treinado: {e}")
            raise

    def cancel_training(self, job_id: str) -> bool:
        """Cancela um treinamento em andamento.

        Args:
            job_id (str): ID do job de treinamento a ser cancelado.

        Returns:
            bool: True se cancelado com sucesso, False caso contrário.

        Raises:
            Exception: Se ocorrer erro ao cancelar o treinamento.
        """
        try:
            client = self.create_api_client_instance()
            if not client.can_train:
                return False
            return client.cancel_training(job_id)
        except Exception as e:
            logger.error(f"Erro ao cancelar treinamento {job_id}: {e}")
            raise

class AITrainingFilesManager(AIClientGlobalConfiguration):
    """Proxy model para gerenciar arquivos de treinamento."""
    
    class Meta:
        proxy = True
        verbose_name = "Arquivos de Treinamento na IA"
        verbose_name_plural = "Arquivos de Treinamento na IA"

class AITrainedModelsManager(AIClientGlobalConfiguration):
    """Proxy model para gerenciar modelos treinados."""
    
    class Meta:
        proxy = True
        verbose_name = "Gerenciador de Modelos Treinados"
        verbose_name_plural = "Gerenciador de Modelos Treinados"

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

    def to_dict(self):
        """Converte a configuração do cliente em um dicionário.

        Returns:
            dict: Dicionário com os atributos da configuração do cliente.
        """
        return {
            'model_name': self.model_name,
            'configurations': self.configurations or {},
            'training_configurations': self.training_configurations or {},
            'use_system_message': self.use_system_message,
        }

    def create_api_client_instance(self, token = None) -> APIClient:
        """Retorna uma instância configurada do cliente de IA.

        Busca automaticamente as configurações de prompt do token associado.

        Args:
            token: Token do usuário, opcional.

        Returns:
            APIClient: Instância configurada do cliente de IA.

        Raises:
            ValueError: Se o cliente não for encontrado no mapeamento.
        """
        client_class = AI_CLIENT_MAPPING.get(self.ai_client.api_client_class)
        
        if not client_class:
            raise ValueError(f"Cliente não encontrado: {self.ai_client.api_client_class}")
        
        # Configuração de prompt padrão como dicionário vazio
        prompt_config = {}
        
        # Se um token foi fornecido, busca as configurações de prompt
        if token:
            try:
                token_config = token.ai_configuration
                if token_config:
                    prompt_config = token_config.to_dict()
            except TokenAIConfiguration.DoesNotExist:
                logger.warning(f"Nenhuma configuração de prompt encontrada para o token {token.name}")
        
        client_config = AIClientConfig(
            ai_global_config=self.ai_client.to_dict(),
            ai_client_config=self.to_dict(),
            prompt_config=prompt_config
        )
            
        return client_class(client_config)
    
    def compare(self, data: dict, token: UserToken) -> dict:
        """Realiza uma comparação de dados usando a IA.

        Args:
            data (dict): Dados a serem comparados.
            token (UserToken): Token do usuário, opcional.

        Returns:
            dict: Resultado da comparação.

        Raises:
            Exception: Se ocorrer erro durante a comparação.
        """
        try:
            client = self.create_api_client_instance(token)
            return client.compare(data)
        except Exception as e:
            logger.error(f"Erro ao comparar dados: {e}")
            raise

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

    def clean(self):
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
        file: Campo de arquivo.
        uploaded_at: Data e hora do upload.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_files')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='training_files/', storage=OverwriteStorage())
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def file_exists(self):
        """Verifica se o arquivo físico existe.
        
        Returns:
            bool: True se o arquivo existir, False caso contrário
        """
        return self.file and self.file.storage.exists(self.file.name)

    def get_file_size(self):
        """Retorna o tamanho do arquivo se ele existir.
        
        Returns:
            int: Tamanho do arquivo em bytes ou 0 se não existir
        """
        try:
            return self.file.size if self.file_exists() else 0
        except Exception:
            return 0

    def __str__(self):
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
def delete_file_on_model_delete(sender, instance, **kwargs):
    """Remove o arquivo físico quando o objeto é deletado.

    Args:
        sender: Classe do modelo.
        instance: Instância do modelo deletado.
        **kwargs: Argumentos adicionais.
    """
    if instance.file:
        if instance.file.storage.exists(instance.file.name):
            instance.file.delete(save=False)
            logger.debug(f"Arquivo físico deletado via sinal: {instance.file.name}")

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
        blank=False,
        null=False,
        help_text='Respostas personalizadas para este token.'
    )

    class Meta:
        verbose_name = "Token - Configuração de Prompt"
        verbose_name_plural = "Token - Configurações de Prompt"

    def __str__(self):
        """Retorna a representação textual da configuração de prompt.

        Returns:
            str: Descrição do token relacionado.
        """
        return f"Configuração de IA para Token: {self.token.name}"

    def clean(self):
        if not self.prompt or not self.prompt.strip():
            raise ValidationError({'prompt': 'O campo Prompt é obrigatório.'})
        
        if not self.responses or not self.responses.strip():
            raise ValidationError({'responses': 'O campo Respostas é obrigatório.'})
        super().clean()

    def to_dict(self):
        """Converte as configurações de prompt em um dicionário.

        Returns:
            dict: Dicionário com as configurações de prompt.
        """
        return {
            'base_instruction': self.base_instruction or "",
            'prompt': self.prompt,
            'responses': self.responses
        }

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
    def _generate_temp_filename(instance, filename):
        """Gera um nome único para o arquivo temporário."""
        ext = filename.split('.')[-1] if '.' in filename else 'tmp'
        filename = f"{uuid.uuid4()}.{ext}"
        return os.path.join('training_captures', filename)

    token = models.ForeignKey(UserToken, related_name='training_captures', on_delete=models.CASCADE)
    ai_client_config = models.ForeignKey('AIClientConfiguration', on_delete=models.CASCADE) 
    is_active = models.BooleanField(default=False)
    temp_file = models.FileField(
        upload_to=_generate_temp_filename,
        null=True,
        blank=True,
        storage=OverwriteStorage()
    )
    create_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('token',)
        verbose_name = "Captura de Treinamento"
        verbose_name_plural = "Capturas de Treinamento"

    def __str__(self):
        """Retorna a representação em string da captura.

        Returns:
            str: Status e informações do token e da IA.
        """
        status = "Ativa" if self.is_active else "Inativa"
        return f"Captura {status} para {self.ai_client_config} do Token {self.token.name}"

    def save(self, *args, **kwargs):
        """Garante que um arquivo temporário seja criado se não existir."""
        if not self.temp_file:
            temp_filename = self._generate_temp_filename("capture.tmp")
            # Cria um arquivo vazio
            with open(os.path.join(settings.MEDIA_ROOT, temp_filename), 'w') as f:
                f.write('')
            self.temp_file.name = temp_filename
        super().save(*args, **kwargs)

@receiver(post_delete, sender=TrainingCapture)
def delete_temp_file_on_delete(sender, instance, **kwargs):
    """Remove o arquivo temporário quando a captura for deletada."""
    if instance.temp_file:
        if instance.temp_file.storage.exists(instance.temp_file.name):
            instance.temp_file.delete(save=False)
            logger.debug(f"Arquivo temporário deletado: {instance.temp_file.name}")

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
    
    def __str__(self):
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

    def __str__(self):
        return f"Treinamento {self.job_id} para {self.ai_config.name}"

    def get_global_client(self):
        """Obtém o cliente global da IA associada."""
        return self.ai_config.ai_client

    def cancel_training(self) -> bool:
        """Cancela o treinamento em andamento.

        Returns:
            bool: True se cancelado com sucesso, False caso contrário.
        """
        if self.status != 'in_progress':
            return False

        try:
            client = self.get_global_client()
            if client.cancel_training(self.job_id):
                self.status = 'failed'
                self.error = 'Treinamento cancelado pelo usuário'
                self.save()
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao cancelar treinamento {self.job_id}: {e}")
            return False

@receiver(post_delete, sender=AITraining)
def delete_model_on_training_delete(sender, instance, **kwargs):
    """Remove o modelo treinado quando um registro de treinamento é excluído."""
    if instance.model_name:
        try:
            global_config = instance.get_global_client()
            global_config.delete_trained_model(instance.model_name)
            logger.info(f"Modelo {instance.model_name} removido com sucesso")
        except Exception as e:
            logger.error(f"Erro ao remover modelo {instance.model_name}: {e}")
