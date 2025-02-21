"""Módulo de modelos para perfis de usuário e tokens.

Contém os modelos Profile (vinculado ao User do Django) e UserToken para controle de tokens da API.
"""

import uuid
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    """Modelo que representa o perfil de um usuário.

    Atributos:
        user (User): Usuário associado.
        is_approved (bool): Indica se o perfil está aprovado.
        capture_inactivity_timeout (int): Tempo de inatividade de captura em minutos.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)
    capture_inactivity_timeout = models.IntegerField(
        default=5,
        verbose_name="Tempo de Inatividade de Captura (minutos)"
    )

    def __str__(self):
        """Retorna a representação em string do perfil.
        
        Retorna:
            str: Email do usuário seguido da palavra 'Profile'.
        """
        return f"{self.user.email} Profile"

class UserToken(models.Model):
    """Representa um token para acesso à API associado a um usuário.

    Atributos:
        id (UUID): Identificador único do token.
        user (User): Usuário proprietário do token.
        name (str): Nome customizado para o token.
        key (str): Chave do token.
        created (datetime): Data de criação do token.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='tokens', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=40, unique=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')

    def save(self, *args, **kwargs):
        """Salva a instância do token, gerando uma chave única se necessário.

        Argumentos:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        
        Retorna:
            None
        """
        if not self.key:
            self.key = self.generate_unique_key()
        super().save(*args, **kwargs)

    def generate_unique_key(self):
        """Gera uma chave hexadecimal única para o token.
        
        Retorna:
            str: Chave única do token.
        """
        key = uuid.uuid4().hex
        while UserToken.objects.filter(key=key).exists():
            key = uuid.uuid4().hex
        return key

    def __str__(self):
        """Retorna a representação em string do token.
        
        Retorna:
            str: Nome do token seguido de sua chave.
        """
        return f"{self.name} - {self.key}"
