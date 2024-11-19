from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_delete
from .storage import OverwriteStorage  # Importe a classe de armazenamento personalizada
import logging

import uuid
from accounts.models import UserToken
from django.contrib.auth import get_user_model

# Configuração do logger
logger = logging.getLogger(__name__)

User = get_user_model()

class AIClient(models.Model):  # Renomeado de AIClientConfiguration e ajustado
    api_client_class = models.CharField(max_length=255, unique=True)
    api_key = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Global - Cliente de IA"
        verbose_name_plural = "Global - Clientes de IA"

    def __str__(self):
        return f"Cliente de IA para {self.api_client_class}"

class AIClientConfiguration(models.Model):  # Renomeado de TokenConfiguration
    token = models.ForeignKey('accounts.UserToken', related_name='configurations', on_delete=models.CASCADE)
    ai_client = models.ForeignKey('AIClient', on_delete=models.CASCADE)  # Agora referencia AIClient
    enabled = models.BooleanField(default=False)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    configurations = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('token', 'ai_client')  # Cada combinação de token e cliente deve ser única
        verbose_name = "Token - Configuração de Cliente de IA"
        verbose_name_plural = "Token - Configurações de Cliente de IA"

    def __str__(self):
        return f"Configuração para {self.ai_client.api_client_class} do Token {self.token.name}"

class AITrainingFile(models.Model):
    """
    Model para armazenar arquivos de treinamento vinculados ao usuário.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='training_files')
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='training_files/', storage=OverwriteStorage())
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Arquivo de Treinamento de {self.user.email} carregado em {self.uploaded_at}"

    class Meta:
        unique_together = ('user', 'name')  # Garante que cada usuário tenha nomes únicos para seus arquivos
        verbose_name = "Arquivo de Treinamento"
        verbose_name_plural = "Arquivos de Treinamento"

@receiver(post_delete, sender=AITrainingFile)
def delete_file_on_model_delete(sender, instance, **kwargs):
    """
    Remove o arquivo físico do sistema de arquivos ao deletar o objeto.
    """
    if instance.file:
        if instance.file.storage.exists(instance.file.name):
            instance.file.delete(save=False)
            logger.debug(f"Arquivo físico deletado via sinal: {instance.file.name}")

class TokenAIConfiguration(models.Model):
    token = models.OneToOneField(UserToken, related_name='ai_configuration', on_delete=models.CASCADE)
    base_instruction = models.TextField(
        blank=True,
        null=True,
        help_text='Instrução base personalizada para este token.'
    )
    prompt = models.TextField(
        blank=True,
        null=True,
        help_text='Prompt personalizado para este token.'
    )
    responses = models.TextField(
        blank=True,
        null=True,
        help_text='Respostas personalizadas para este token.'
    )
    training_file = models.ForeignKey(
        AITrainingFile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Selecione o arquivo de treinamento para este token.'
    )

    class Meta:
        verbose_name = "Token - Configuração de Prompt"
        verbose_name_plural = "Token - Configurações de Prompt"

    def __str__(self):
        return f"Configuração de IA para Token: {self.token.name}"

class AIClientTraining(models.Model):
    """
    Model para armazenar parâmetros de treinamento e nome do modelo treinado para cada AIClientConfiguration.
    """
    ai_client_configuration = models.OneToOneField(AIClientConfiguration, on_delete=models.CASCADE, related_name='training')
    training_parameters = models.JSONField(default=dict, blank=True, help_text="Parâmetros de treinamento para esta configuração de cliente de IA.")
    trained_model_name = models.CharField(max_length=255, blank=True, null=True, editable=False, help_text="Nome do modelo treinado. Não é editável pelo administrador.")

    def __str__(self):
        return f"Treinamento para {self.ai_client_configuration.ai_client.api_client_class} do Token {self.ai_client_configuration.token.name}"

    class Meta:
        verbose_name = "Token - Parâmetros de Treinamento de IA"
        verbose_name_plural = "Token - Parâmetros de Treinamento de IA"

class DocumentAIConfiguration(models.Model):
    project_id = models.CharField(max_length=100)
    location = models.CharField(max_length=50)
    processor_id = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Configuração de Processamento de Documento"
        verbose_name_plural = "Configurações de Processamento de Documento"

    def __str__(self):
        return f"DocumentAI Configuração ({self.project_id})"

class TrainingCapture(models.Model):
    token = models.ForeignKey(UserToken, related_name='training_captures', on_delete=models.CASCADE)
    ai_client = models.ForeignKey('AIClient', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ('token', 'ai_client')
        verbose_name = "Captura de Treinamento"
        verbose_name_plural = "Capturas de Treinamento"

    def __str__(self):
        status = "Ativa" if self.is_active else "Inativa"
        return f"Captura {status} para {self.ai_client} do Token {self.token.name}"