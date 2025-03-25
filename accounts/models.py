"""
Módulo de modelos para perfis de usuário e tokens.

Contém os modelos Profile (vinculado ao User do Django) e UserToken para controle de tokens da API.

A documentação segue o padrão Google e os logs são gerados de forma padronizada.
"""

import uuid
import logging
from django.db import models
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class Profile(models.Model):
    """Modelo que representa o perfil de um usuário.

    Estende o modelo User padrão do Django com campos adicionais específicos.

    Attributes:
        user (User): Usuário associado (relacionamento 1:1).
        is_approved (bool): Indica se o perfil está aprovado pelo administrador.
        capture_inactivity_timeout (int): Tempo de inatividade de captura em minutos.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)
    capture_inactivity_timeout = models.IntegerField(
        default=5,
        verbose_name="Tempo de Inatividade de Captura (minutos)"
    )

    def __str__(self) -> str:
        """Retorna a representação em string do perfil.

        Returns:
            str: Email do usuário seguido de 'Profile'.
        """
        return f"{self.user.email} Profile"

    def save(self, *args, **kwargs):
        """Salva o perfil com log apropriado.

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        is_new = self._state.adding
        try:
            super().save(*args, **kwargs)
            action = "criado" if is_new else "atualizado"
            logger.info(f"Perfil {action} para usuário: {self.user.email}")
        except Exception as e:
            logger.error(f"Erro ao salvar perfil para {self.user.email}: {str(e)}", exc_info=True)
            raise


class UserToken(models.Model):
    """Representa um token para acesso à API associado a um usuário.

    Cada usuário pode ter múltiplos tokens para diferentes fins.

    Attributes:
        id (UUID): Identificador único do token.
        user (User): Usuário proprietário do token.
        name (str): Nome customizado para o token.
        key (str): Chave do token (gerada automaticamente).
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

        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        is_new = not self.key
        try:
            if is_new:
                self.key = self.generate_unique_key()
            super().save(*args, **kwargs)
            if is_new:
                logger.info(f"Novo token '{self.name}' criado para usuário: {self.user.email}")
            else:
                logger.info(f"Token '{self.name}' atualizado para usuário: {self.user.email}")
        except Exception as e:
            logger.error(f"Erro ao salvar token '{self.name}': {str(e)}", exc_info=True)
            raise

    def generate_unique_key(self) -> str:
        """Gera uma chave hexadecimal única para o token.

        Returns:
            str: Chave única do token.

        Raises:
            Exception: Se houver erro ao gerar a chave.
        """
        try:
            key = uuid.uuid4().hex
            attempt = 1
            while UserToken.objects.filter(key=key).exists():
                if attempt > 5:
                    logger.warning("Múltiplas tentativas de geração de chave de token")
                key = uuid.uuid4().hex
                attempt += 1
            return key
        except Exception as e:
            logger.error(f"Erro ao gerar chave para token: {str(e)}", exc_info=True)
            raise

    def __str__(self) -> str:
        """Retorna a representação em string do token.

        Returns:
            str: Nome do token seguido dos 8 primeiros dígitos da chave.
        """
        return f"{self.name} - {self.key[:8]}..."
