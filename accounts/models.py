# accounts/models.py

from django.db import models
from django.contrib.auth.models import User
import uuid

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} Profile"

class UserToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='tokens', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=40, unique=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')  # Garantir que o nome do token seja único por usuário

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_unique_key()
        super().save(*args, **kwargs)

    def generate_unique_key(self):
        key = uuid.uuid4().hex
        while UserToken.objects.filter(key=key).exists():
            key = uuid.uuid4().hex
        return key

    def __str__(self):
        return f"{self.name} - {self.key}"

class AIClientConfiguration(models.Model):
    api_client_class = models.CharField(max_length=255, unique=True)
    api_key = models.CharField(max_length=255)
    model_name = models.CharField(max_length=255)
    configurations = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Configuração Padrão para {self.api_client_class}"

class TokenConfiguration(models.Model):
    token = models.ForeignKey(UserToken, related_name='configurations', on_delete=models.CASCADE)
    api_client_class = models.CharField(max_length=255)
    enabled = models.BooleanField(default=False)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    configurations = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('token', 'api_client_class')  # Cada combinação de token e classe deve ser única

    def __str__(self):
        return f"Configuração para {self.api_client_class} do Token {self.token.name}"
