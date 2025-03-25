"""Modelos de dados da API.

Define as estruturas de dados persistentes usadas pela API,
incluindo logs de requisições e outras entidades relacionadas.
"""

import logging
from typing import Any, Dict, Optional
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from accounts.models import UserToken
from core.exceptions import ApplicationError
from core.types.monitoring import APILog as APILogType, HTTP_METHODS
from core.types.async_task import AsyncComparisonTask, AsyncTaskStatus

logger = logging.getLogger(__name__)

class APILog(models.Model):
    """Registro de requisições à API.
    
    Armazena informações detalhadas sobre cada requisição feita à API,
    permitindo auditoria, análise e debug de problemas.
    
    Attributes:
        user: Usuário que realizou a requisição (opcional).
        user_token: Token utilizado na autenticação (opcional).
        path: Caminho da URL solicitada.
        method: Método HTTP da requisição (GET, POST, etc).
        request_body: Corpo da requisição (opcional).
        response_body: Corpo da resposta (opcional).
        status_code: Código de status HTTP retornado.
        execution_time: Tempo de processamento em segundos.
        requester_ip: Endereço IP do requisitante (opcional).
        timestamp: Data e hora da requisição.
    """
    
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
            models.Index(fields=['user_token']),
            models.Index(fields=['status_code']),
            models.Index(fields=['method']),
            models.Index(fields=['path']),
        ]

    def __str__(self) -> str:
        """Representação em string do log.
        
        Returns:
            str: Representação textual do registro de log.
        """
        return f"[{self.timestamp}] {self.method} {self.path} ({self.status_code})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Salva o log com registro apropriado.
        
        Args:
            *args: Argumentos posicionais para o método save() original.
            **kwargs: Argumentos nomeados para o método save() original.
        
        Raises:
            ApplicationError: Se ocorrer erro ao salvar o log.
        """
        try:
            logger.debug(f"Salvando log de API: {self.method} {self.path}")
            super().save(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Erro ao salvar log de API: {str(e)}")
            raise ApplicationError(f"Erro ao registrar log de API: {str(e)}")

    def to_log_data(self) -> APILogType:
        """Converte o modelo para o tipo APILog.
        
        Transforma a instância do modelo Django em uma estrutura de dados
        tipada para uso em outras partes da aplicação.
        
        Returns:
            APILogType: Objeto tipado com os dados do log.
        
        Raises:
            ApplicationError: Se ocorrer erro durante a conversão.
        """
        try:
            return APILogType(
                id=self.id,
                user_token=self.user_token.key if self.user_token else None,
                request_method=self.method,
                request_path=self.path,
                request_body=self.request_body,
                response_body=self.response_body,
                status_code=self.status_code,
                execution_time=self.execution_time,
                requester_ip=self.requester_ip or "",
                timestamp=self.timestamp
            )
        except Exception as e:
            logger.exception(f"Erro ao converter modelo para APILogType: {str(e)}")
            raise ApplicationError(f"Erro na conversão de tipo de log: {str(e)}")
            
    @classmethod
    def create_from_request(cls, request: Any, response: Any, execution_time: float) -> 'APILog':
        """Cria um registro de log a partir de uma requisição e resposta.
        
        Args:
            request: Objeto de requisição HTTP.
            response: Objeto de resposta HTTP.
            execution_time: Tempo de execução em segundos.
            
        Returns:
            APILog: Instância do modelo APILog criada.
            
        Raises:
            ApplicationError: Se ocorrer erro durante a criação.
        """
        try:
            # Extrair token se existir
            token = None
            user = None
            auth_header = request.headers.get('Authorization', '')
            
            if auth_header.startswith('Token '):
                token_key = auth_header.replace('Token ', '')
                try:
                    token = UserToken.objects.select_related('user').get(key=token_key)
                    user = token.user
                except UserToken.DoesNotExist:
                    pass
            
            # Obter corpo da requisição
            body = getattr(request, '_body', b'').decode('utf-8', errors='replace') if hasattr(request, '_body') else None
            
            # Obter corpo da resposta
            response_content = response.content.decode('utf-8', errors='replace') if hasattr(response, 'content') else None
            
            # Criar o log
            log = cls(
                user=user,
                user_token=token,
                path=request.path,
                method=request.method,
                request_body=body,
                response_body=response_content,
                status_code=response.status_code,
                execution_time=execution_time,
                requester_ip=request.META.get('REMOTE_ADDR')
            )
            log.save()
            
            return log
            
        except ApplicationError:
            raise
        except Exception as e:
            logger.exception(f"Erro ao criar log de API: {str(e)}")
            raise ApplicationError(f"Erro ao registrar requisição API: {str(e)}")

class AsyncTaskRecord(models.Model):
    """Registro de tarefas assíncronas.
    
    Armazena informações sobre tarefas que estão sendo processadas de forma
    assíncrona pelo Celery, permitindo consulta do status e resultado.
    
    Attributes:
        task_id: Identificador único da tarefa.
        status: Estado atual da tarefa (pending, processing, completed, failed).
        user: Usuário que iniciou a tarefa.
        user_token: Token utilizado para autenticar a requisição.
        input_data: Dados de entrada da tarefa (JSON).
        result: Resultado da tarefa quando concluída (JSON).
        error: Mensagem de erro se a tarefa falhou.
        created_at: Data e hora de criação da tarefa.
        updated_at: Data e hora da última atualização.
    """
    
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    EXPIRED = 'expired'
    
    STATUS_CHOICES = [
        (PENDING, 'Pendente'),
        (PROCESSING, 'Em Processamento'),
        (COMPLETED, 'Concluída'),
        (FAILED, 'Falha'),
        (EXPIRED, 'Expirada'),
    ]
    
    task_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="ID da Tarefa"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        verbose_name="Status"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='async_tasks',
        verbose_name="Usuário"
    )
    user_token = models.ForeignKey(
        UserToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='async_tasks',
        verbose_name="Token"
    )
    input_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Dados de Entrada"
    )
    result = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resultado"
    )
    error = models.TextField(
        null=True,
        blank=True,
        verbose_name="Erro"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Tarefa Assíncrona"
        verbose_name_plural = "Tarefas Assíncronas"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_id']),
            models.Index(fields=['status']),
            models.Index(fields=['user']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Tarefa {self.task_id} ({self.get_status_display()})"
    
    def to_core_type(self) -> AsyncComparisonTask:
        """Converte para o tipo AsyncTask do core.
        
        Returns:
            AsyncComparisonTask: Instância do tipo core para esta tarefa.
        """
        # Mapeia status do modelo para enums do core
        status_map = {
            self.PENDING: AsyncTaskStatus.PENDING,
            self.PROCESSING: AsyncTaskStatus.PROCESSING,
            self.COMPLETED: AsyncTaskStatus.COMPLETED,
            self.FAILED: AsyncTaskStatus.FAILED,
            self.EXPIRED: AsyncTaskStatus.EXPIRED
        }
        
        return AsyncComparisonTask(
            task_id=self.task_id,
            status=status_map[self.status],
            created_at=self.created_at,
            updated_at=self.updated_at,
            input_data=self.input_data,
            result=self.result,
            error=self.error,
            user_id=self.user_id,
            user_token_id=self.user_token_id if self.user_token else None
        )
