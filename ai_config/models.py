"""Modelos para configuração e gerenciamento de IAs.

Define os modelos de dados para configurações de IA, arquivos de treinamento,
e gerenciamento de modelos treinados.
"""
from datetime import time
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import uuid
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from django.dispatch import receiver

from accounts.models import UserToken
from core.exceptions import APICommunicationError
from core.validators import validate_training_file_content

from api.utils.clientsIA import AI_CLIENT_MAPPING, APIClient
from core.types import (
    AIConfig,
    AIPromptConfig,
    AISingleComparisonData, 
    AITrainingFileData, 
    AITrainingStatus,
    AITrainingResponse,
    AITrainingExampleCollection,
)

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
                    prompt_config = AIPromptConfig(
                        base_instruction=token_config.base_instruction,
                        prompt=token_config.prompt,
                        response=token_config.responses
                    )
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
        file: Campo de arquivo.
        uploaded_at: Data e hora do upload.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_files')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='training_files/', storage=OverwriteStorage())
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def file_exists(self) -> bool:
        """Verifica se o arquivo físico existe.
        
        Returns:
            bool: True se o arquivo existir, False caso contrário
        """
        return self.file and self.file.storage.exists(self.file.name)

    def get_file_size(self) -> int:
        """Retorna o tamanho do arquivo se ele existir.
        
        Returns:
            int: Tamanho do arquivo em bytes ou 0 se não existir
        """
        try:
            return self.file.size if self.file_exists() else 0
        except Exception:
            return 0

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

    def get_file_data(self) -> AITrainingFileData:
        """Retorna os dados do arquivo no formato estruturado.
        
        Returns:
            AITrainingFileData: Dados estruturados do arquivo
        """
        return AITrainingFileData(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            file_path=self.file.path,
            uploaded_at=self.uploaded_at,
            file_size=self.get_file_size()
        )

@receiver(post_delete, sender=AITrainingFile)
def delete_file_on_model_delete(sender: Any, instance: 'AITrainingFile', **kwargs: Any) -> None:
    """Remove o arquivo físico quando o modelo é excluído."""
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        except Exception as e:
            logger.error(f"Erro ao remover arquivo {instance.file.path}: {e}")

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

    def to_dict(self) -> AIPromptConfig:
        """Converte a configuração para um dicionário adequado."""
        return AIPromptConfig(
            base_instruction=self.base_instruction or "",
            prompt=self.prompt,
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
    def _generate_temp_filename(instance: 'TrainingCapture', filename: str) -> str:
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

    def __str__(self) -> str:
        """Retorna a representação em string da captura.

        Returns:
            str: Status e informações do token e da IA.
        """
        status = "Ativa" if self.is_active else "Inativa"
        return f"Captura {status} para {self.ai_client_config} do Token {self.token.name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Garante que um arquivo temporário seja criado se não existir."""
        if not self.temp_file:
            temp_filename = self._generate_temp_filename("capture.tmp")
            # Cria um arquivo vazio
            with open(os.path.join(settings.MEDIA_ROOT, temp_filename), 'w') as f:
                f.write('')
            self.temp_file.name = temp_filename
        super().save(*args, **kwargs)

    def get_examples_collection(self) -> AITrainingExampleCollection:
        """Retorna uma coleção de exemplos de treinamento baseada no arquivo temporário.
        
        Se o arquivo temporário não existir, ele será criado automaticamente.
        A coleção retornada permite gerenciar (carregar, adicionar, remover, salvar) exemplos
        de treinamento associados a esta captura.
        
        Returns:
            AITrainingExampleCollection: Coleção de exemplos de treinamento
        """
        if not self.temp_file:
            self.save()
        
        # Obter o caminho completo para o arquivo
        file_path = self.temp_file.path
        
        # Criar e retornar a coleção de exemplos
        return AITrainingExampleCollection(file_path=file_path)

@receiver(post_delete, sender=TrainingCapture)
def delete_temp_file_on_delete(sender: Any, instance: 'TrainingCapture', **kwargs: Any) -> None:
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
