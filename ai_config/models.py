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
from django.utils import timezone
from django.conf import settings

from accounts.models import UserToken

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

class AIClientConfiguration(models.Model):
    """Configuração específica vinculada a um token e um cliente global de IA.

    Attributes:
        token: Referência ao token do usuário.
        ai_client: Referência à configuração global de IA.
        name (str): Nome personalizado da IA.
        enabled (bool): Indica se está habilitada.
        model_name (str): Nome do modelo (opcional).
        configurations (dict): Configurações adicionais em JSON.
        use_system_message (bool): Indica se deve usar a mensagem do sistema.
    """
    token = models.ForeignKey('accounts.UserToken', related_name='configurations', on_delete=models.CASCADE)
    ai_client = models.ForeignKey('AIClientGlobalConfiguration', on_delete=models.CASCADE)
    name = models.CharField("Nome da IA (personalizado)", max_length=100)
    enabled = models.BooleanField(default=False)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    configurations = models.JSONField(default=dict, blank=True)
    use_system_message = models.BooleanField(
         default=False,
         verbose_name="Usar System Message",
         help_text="Indica se deve utilizar a mensagem do sistema, se suportado pela API."
    )
    class Meta:
        unique_together = ('token', 'name')
        verbose_name = "Token - Configuração de Cliente de IA"
        verbose_name_plural = "Token - Configurações de Cliente de IA"
    def __str__(self):
        """Representação textual da configuração do cliente de IA.

        Returns:
            str: Informação sobre o token e a classe de IA.
        """
        return f"[{self.token.name}] {self.name} -> {self.ai_client.api_client_class}"


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
        prompt (str): Prompt personalizado (opcional).
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
        super().clean()

class AIClientTraining(models.Model):
    """Parâmetros de treinamento e nome do modelo treinado para uma configuração de IA.

    Attributes:
        ai_client_configuration: Configuração do cliente de IA vinculada.
        training_parameters (dict): Parâmetros de treinamento.
        trained_model_name (str): Nome do modelo treinado (somente leitura).
    """
    ai_client_configuration = models.OneToOneField(AIClientConfiguration, on_delete=models.CASCADE, related_name='training')
    training_parameters = models.JSONField(default=dict, blank=True, help_text="Parâmetros de treinamento para esta configuração de cliente de IA.")
    trained_model_name = models.CharField(max_length=255, blank=True, null=True, editable=False, help_text="Nome do modelo treinado. Não é editável pelo administrador.")

    def __str__(self):
        """Retorna a representação textual do treinamento.

        Returns:
            str: Informações sobre o treinamento e o token.
        """
        return f"Treinamento para {self.ai_client_configuration.ai_client.api_client_class} do Token {self.ai_client_configuration.token.name}"

    class Meta:
        verbose_name = "Token - Parâmetros de Treinamento de IA"
        verbose_name_plural = "Token - Parâmetros de Treinamento de IA"

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
