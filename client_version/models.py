from django.db import models
from django.utils import timezone

class ClientVersion(models.Model):
    """Modelo para armazenar informações de versão do cliente."""
    product_name = models.CharField(max_length=100, help_text="Nome do produto ou cliente")
    version = models.CharField(max_length=50, help_text="Número da versão (ex: 1.0.0)")
    release_date = models.DateTimeField(default=timezone.now)
    download_url = models.URLField(max_length=500, help_text="URL para download do cliente")
    is_mandatory = models.BooleanField(default=False, help_text="Se a atualização é obrigatória")
    release_notes = models.TextField(blank=True, help_text="Notas de lançamento desta versão")
    active = models.BooleanField(default=True, help_text="Se esta versão está ativa")
    
    class Meta:
        verbose_name = "Versão do Cliente"
        verbose_name_plural = "Versões dos Clientes"
        ordering = ['-release_date']
    
    def __str__(self):
        return f"{self.product_name} v{self.version}"
