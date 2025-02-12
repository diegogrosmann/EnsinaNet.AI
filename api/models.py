"""
Módulo de modelos da aplicação API.

(NOVO) Adicionamos campo 'user' em APILog, para salvar o usuário no log.
"""

from django.db import models
from django.contrib.auth.models import User  # (NOVO) Para armazenar user
from accounts.models import UserToken


class APILog(models.Model):
    """
    Registra cada requisição de API para fins de monitoramento em tempo real.

    Atributos:
        user (User): Usuário autenticado, se houver.
        user_token (UserToken): Token do usuário, se encontrado.
        path (str): Caminho da URL requisitada.
        method (str): Método HTTP (GET, POST etc.).
        status_code (int): Código de status da resposta.
        execution_time (float): Tempo total de processamento.
        timestamp (datetime): Momento em que foi criado o log.
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # (NOVO)
    user_token = models.ForeignKey(UserToken, on_delete=models.SET_NULL, null=True, blank=True)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    execution_time = models.FloatField(help_text="Tempo em segundos para processar a requisição.")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Retorna uma string representando o log."""
        return f"[{self.timestamp}] {self.method} {self.path} ({self.status_code})"
