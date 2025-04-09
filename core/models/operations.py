"""Modelos de dados da API para operações de longa duração."""

import uuid
from django.db import models
from django.utils import timezone
import logging

from accounts.models import UserToken
from core.types import OperationData, OperationType, EntityStatus
from core.types.task import TaskDict

logger = logging.getLogger(__name__)

ENTITY_STATUS_CHOICES = [(s.value, s.name) for s in EntityStatus]
OPERATION_TYPE_CHOICES = [(t.value, t.name) for t in OperationType]

class Operation(models.Model):
    """Representa uma operação de longa duração.
    
    Armazena informações básicas sobre uma operação assíncrona iniciada pelo usuário,
    como comparações ou treinamentos de IA. Os detalhes do estado atual são computados
    dinamicamente pelas tarefas associadas.
    
    Attributes:
        operation_id: Identificador único da operação (UUID).
        operation_type: Tipo da operação (ex: "comparison", "training").
        user_token: Token usado para autenticar a requisição.
        created_at: Data e hora de criação da operação.
        expiration: Data e hora de expiração da operação.
    """
    
    operation_id = models.CharField(
        max_length=255,
        unique=True,
        default=uuid.uuid4,
        verbose_name="ID da Operação"
    )
    operation_type = models.CharField(
        max_length=50,
        choices=OPERATION_TYPE_CHOICES,
        verbose_name="Tipo de Operação"
    )
    user_token = models.ForeignKey(
        UserToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operations',
        verbose_name="Token"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    expiration = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expiração"
    )
    
    class Meta:
        verbose_name = "Operação"
        verbose_name_plural = "Operações"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['operation_id']),
            models.Index(fields=['operation_type']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Operação {self.operation_id} ({self.operation_type})"
    
    def to_operation_data(self) -> OperationData:
        """Converte o modelo de dados para um objeto OperationData.
        
        Carrega todas as tarefas associadas e deixa que o OperationData 
        calcule o status e progresso atual baseado nas tarefas.
        
        Returns:
            OperationData: Representação da operação como objeto de domínio.
        """
        # Converter tipo de operação para enum
        op_type = OperationType(self.operation_type)
        
        # Obter user_id do token se disponível
        user_id = None
        if self.user_token and hasattr(self.user_token, 'user'):
            user_id = self.user_token.user.id
        
        # Obter e converter tarefas associadas
        tasks = self._load_tasks()
        
        # Criar a instância de OperationData
        operation_data = OperationData(
            user_id=user_id,
            user_token_id=self.user_token.key if self.user_token else "",
            operation_type=op_type,
            operation_id=self.operation_id,
            created_at=self.created_at,
            updated_at=timezone.now(),  # Usa o tempo atual como última atualização
            expiration=self.expiration,
            tasks=tasks
        )
        
        logger.debug(f"Convertido Operation {self.operation_id} para OperationData com {len(tasks) if tasks else 0} tarefas")
        return operation_data
    
    def _load_tasks(self) -> TaskDict:
        """Carrega todas as tarefas associadas a esta operação.
        
        Returns:
            TaskDict: Dicionário de tarefas associadas à operação.
        """
        from core.models.async_task_record import AsyncTaskRecord
        
        tasks_dict = TaskDict()
        
        # Buscar todas as tarefas associadas a esta operação
        async_tasks = AsyncTaskRecord.objects.filter(operation=self)
        
        for task_record in async_tasks:
            try:
                # Converter cada registro para AsyncTask
                task = task_record.to_async_task()
                # Adicionar ao dicionário usando o task_id como chave
                tasks_dict.put_item(task.task_id, task)
            except Exception as e:
                logger.error(f"Erro ao carregar tarefa {task_record.task_id} para operação {self.operation_id}: {str(e)}")
        
        logger.debug(f"Carregadas {len(tasks_dict)} tarefas para operação {self.operation_id}")
        return tasks_dict
    
    @classmethod
    def from_operation_data(cls, operation_data: OperationData) -> 'Operation':
        """Cria ou atualiza um modelo Operation a partir de um OperationData.
        
        Args:
            operation_data: Objeto OperationData com os dados da operação.
            
        Returns:
            Operation: Instância do modelo Operation salva no banco.
        """
        # Buscar instância existente ou criar nova
        try:
            operation = cls.objects.get(operation_id=operation_data.operation_id)
            logger.debug(f"Encontrada operação existente: {operation_data.operation_id}")
        except cls.DoesNotExist:
            operation = cls(operation_id=operation_data.operation_id)
            logger.debug(f"Criando nova operação: {operation_data.operation_id}")

        # Buscar token de usuário
        try:
            user_token = UserToken.objects.get(key=operation_data.user_token_id)
        except UserToken.DoesNotExist:
            logger.warning(f"Token não encontrado: {operation_data.user_token_id}")
            user_token = None
        
        # Atualizar campos da operação
        operation.user_token = user_token
        operation.operation_type = operation_data.operation_type.value
        operation.expiration = operation_data.expiration
        operation.save()
        
        # Salvar tarefas associadas
        if operation_data.tasks and hasattr(operation_data.tasks, '_items') and operation_data.tasks._items:
            from core.models.async_task_record import AsyncTaskRecord
            
            for task_id, task in operation_data.tasks._items.items():
                try:
                    AsyncTaskRecord.from_async_task(task, operation)
                    logger.debug(f"Tarefa {task_id} salva para operação {operation.operation_id}")
                except Exception as e:
                    logger.error(f"Erro ao salvar tarefa {task_id} para operação {operation.operation_id}: {str(e)}")
                    
        return operation