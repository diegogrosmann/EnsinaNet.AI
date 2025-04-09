"""Modelos de dados da API para tarefas assíncronas."""

import logging
import uuid
from django.db import models

from accounts.models import UserToken
from core.models.operations import Operation
from core.types import EntityStatus, AsyncTask,APPError, TaskError, OperationType
from core.types.base import BaseModel

logger = logging.getLogger(__name__)

STATUS_CHOICES = [
    (status.value, status.name.replace('_', ' ').title())
    for status in EntityStatus
]

class AsyncTaskRecord(models.Model):
    """Registro de tarefas assíncronas.
    
    Armazena informações sobre tarefas que estão sendo processadas de forma
    assíncrona pelo Celery, permitindo consulta do status e resultado.
    
    Attributes:
        task_id: Identificador único da tarefa.
        status: Estado atual da tarefa (pending, processing, completed, failed).
        input_data: Dados de entrada da tarefa (JSON).
        result: Resultado da tarefa quando concluída (JSON).
        error: Mensagem de erro se a tarefa falhou.
        created_at: Data e hora de criação da tarefa.
        updated_at: Data e hora da última atualização.
        operation: Operação relacionada a esta tarefa.
    """
    
    task_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="ID da Tarefa"
    )
    operation = models.ForeignKey(
        Operation,
        on_delete=models.CASCADE,
        related_name='async_tasks',
        verbose_name="Operação"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=EntityStatus.PENDING.value,
        verbose_name="Status"
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
    progress = models.FloatField(
        default=0.0,
        verbose_name="Progresso (%)"
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
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Tarefa {self.task_id} ({self.get_status_display()})"
    
    def to_async_task(self) -> AsyncTask:
        """Converte para o tipo AsyncTask do core.
        
        Returns:
            AsyncTask: Instância do tipo core para esta tarefa.
        """
        try:
            # Converter string de status para enum diretamente
            try:
                status = EntityStatus(self.status)
            except ValueError:
                logger.warning(f"Status inválido encontrado no banco: {self.status}, usando PENDING")
                status = EntityStatus.PENDING
            
            result = None
            if self.result:
                # Se o resultado for um dicionário, converte para JSON
                result = BaseModel.from_dict(self.result)
            
            input_data = None
            if self.input_data:
                # Se os dados de entrada forem um dicionário, converte para JSON
                input_data = BaseModel.from_dict(self.input_data)

            # Criar objeto TaskError se existe erro
            task_error = None
            if self.error:
                task_error = TaskError(
                    message=self.error,
                    task_id=self.task_id,
                    error_id=str(uuid.uuid4()),
                    code="database_record_error"
                )
            
            
            # Obter token e user_id da operação se disponível
            token_key = None
            user_id = None
            
            if self.operation and hasattr(self.operation, 'user_token') and self.operation.user_token:
                user_token = self.operation.user_token
                token_key = user_token.key
                if hasattr(user_token, 'user') and user_token.user:
                    user_id = user_token.user.id
            
            # Cria uma instância de AsyncTask com os dados do registro
            return AsyncTask(
                task_id=self.task_id,
                operation_id=self.operation.operation_id,
                status=status,
                created_at=self.created_at,
                updated_at=self.updated_at,
                input_data=input_data,
                result=result,
                error=task_error,
                user_id=user_id,
                token_key=token_key,
                progress=self.progress
            )
        except Exception as e:
            error = APPError(
                message=f"Erro ao converter AsyncTaskRecord para AsyncTask: {str(e)}",
                code='task_conversion_error',
                error_id=str(uuid.uuid4()),
                status_code=500
            )
            logger.error(f"Falha na conversão de tarefa: {error.message}", exc_info=True)
            error.handle()
            raise

    
    @classmethod
    def from_async_task(cls, task: AsyncTask, operation: Operation = None) -> 'AsyncTaskRecord':
        """Cria ou atualiza um registro a partir de um AsyncTask.
        
        Args:
            task: AsyncTask do core.
            operation: Operação relacionada (opcional, se não fornecido será buscado pelo ID).
            
        Returns:
            AsyncTaskRecord: Registro persistido no banco de dados.
        """
        try:
            # Usar a operação fornecida ou buscar/criar uma nova
            if operation is None:
                # Buscar ou criar operação diretamente
                if task.operation_id:
                    operation, _ = Operation.objects.get_or_create(
                        operation_id=task.operation_id,
                        defaults={
                            'operation_type': getattr(task, 'operation_type', OperationType.GENERIC).value
                        }
                    )
                else:
                    # Criar nova operação se não tiver ID
                    operation = Operation.objects.create(
                        operation_type=getattr(task, 'operation_type', OperationType.GENERIC).value
                    )
                
                # Buscar token do usuário para associar à operação
                if task.token_key:
                    try:
                        user_token = UserToken.objects.get(key=task.token_key)
                        operation.user_token = user_token
                        operation.save()
                    except UserToken.DoesNotExist:
                        logger.warning(f"Token {task.token_key} não encontrado")
            
            # Tenta obter registro existente ou cria um novo
            record, created = cls.objects.get_or_create(
                task_id=task.task_id,
                defaults={
                    'status': task.status.value,
                    'operation': operation,
                    'input_data': task.input_data.to_dict() if hasattr(task.input_data, 'to_dict') else task.input_data,
                    'result': task.result.to_dict() if hasattr(task.result, 'to_dict') else task.result,
                    'error': str(task.error) if task.error else None,
                    'progress': task.progress
                }
            )
            
            # Se registro já existia, atualiza os campos
            if not created:
                record.status = task.status.value
                record.progress = task.progress
                
                if task.result:
                    record.result = task.result.to_dict() if hasattr(task.result, 'to_dict') else task.result
                    
                if task.error:
                    record.error = str(task.error)
                    
                # Ao salvar, o método save() vai acionar a atualização da operação
                record.save()
            else:
                # Para registros novos, não tentamos atualizar estado (removida referência a state)
                pass
            
            return record
        except Exception as e:
            error = APPError(
                message=f"Erro ao criar/atualizar registro de tarefa: {str(e)}",
                code='task_record_creation_error',
                error_id=str(uuid.uuid4()),
                status_code=500
            )
            logger.error(error.message, exc_info=True)
            error.handle()
            raise
