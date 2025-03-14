"""Modelos de dados da API."""

import logging
from typing import Any
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from accounts.models import UserToken
from core.types import APILog, HTTP_METHODS

logger = logging.getLogger(__name__)

class APILog(models.Model):
    """Registro de requisições à API."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuário",
        help_text="Usuário que fez a requisição"
    )
    user_token = models.ForeignKey(
        UserToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Token",
        help_text="Token usado na requisição"
    )
    path = models.CharField(
        max_length=255,
        verbose_name="Caminho",
        help_text="URL da requisição"
    )
    method = models.CharField(
        max_length=10,
        choices=HTTP_METHODS,
        verbose_name="Método",
        help_text="Método HTTP"
    )
    request_body = models.TextField(
        null=True,
        blank=True,
        verbose_name="Corpo da Requisição"
    )
    response_body = models.TextField(
        null=True,
        blank=True,
        verbose_name="Corpo da Resposta"
    )
    status_code = models.IntegerField(
        validators=[MinValueValidator(100)],
        verbose_name="Status",
        help_text="Código de status HTTP"
    )
    execution_time = models.FloatField(
        validators=[MinValueValidator(0.0)],
        verbose_name="Tempo",
        help_text="Tempo de execução em segundos"
    )
    requester_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP",
        help_text="Endereço IP do requisitante"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data/Hora",
        help_text="Momento do registro"
    )

    class Meta:
        verbose_name = "Log de API"
        verbose_name_plural = "Logs de API"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['method']),
            models.Index(fields=['status_code']),
        ]

    def __str__(self) -> str:
        """Representação em string do log."""
        return f"[{self.timestamp}] {self.method} {self.path} ({self.status_code})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva o log com registro apropriado."""
        try:
            super().save(*args, **kwargs)
            logger.debug(
                f"Log salvo: {self.method} {self.path} "
                f"[status={self.status_code}, tempo={self.execution_time:.3f}s]"
            )
        except Exception as e:
            logger.error(f"Erro ao salvar log: {e}")
            raise

    def to_log_data(self) -> APILog:
        """Converte o modelo para o tipo APILog."""
        return APILog(
            id=self.id,
            user_token=self.user_token.key if self.user_token else None,
            request_method=self.method,
            request_path=self.path,
            request_body=self.request_body,
            response_body=self.response_body,
            status_code=self.status_code,
            execution_time=self.execution_time,
            requester_ip=self.requester_ip,
            timestamp=self.timestamp
        )
