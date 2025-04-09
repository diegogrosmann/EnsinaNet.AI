"""
Tipos para gerenciamento de filas e tarefas assíncronas.

Define estruturas de dados para representar tarefas executáveis
em background e configurações de filas de processamento.
"""
import logging
from typing import Callable, Optional, Any
from dataclasses import dataclass, field

from core.types.status import EntityStatus
from .base import BaseModel
from .task import QueueableTask, QueueConfig
from core.exceptions import CoreTypeException

logger = logging.getLogger(__name__)


@dataclass
class QueueStats(BaseModel):
    """Estatísticas de uma fila de processamento.
    
    Armazena métricas e informações sobre o estado atual
    e histórico de processamento de uma fila.
    
    Attributes:
        queue_name (str): Nome da fila.
        pending_tasks (int): Número de tarefas aguardando processamento.
        in_progress_tasks (int): Número de tarefas em processamento.
        completed_tasks (int): Número de tarefas concluídas com sucesso.
        failed_tasks (int): Número de tarefas que falharam.
        retry_tasks (int): Número de tarefas aguardando nova tentativa.
        avg_processing_time (float): Tempo médio de processamento em segundos.
    """
    queue_name: str
    pending_tasks: int = 0
    in_progress_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    retry_tasks: int = 0
    avg_processing_time: float = 0.0
    
    def __post_init__(self):
        """Valida os valores após inicialização."""
        if not isinstance(self.queue_name, str):
            raise CoreTypeException("queue_name deve ser uma string")
        
        if not isinstance(self.pending_tasks, int):
            raise CoreTypeException("pending_tasks deve ser um inteiro")
        
        if not isinstance(self.in_progress_tasks, int):
            raise CoreTypeException("in_progress_tasks deve ser um inteiro")
        
        if not isinstance(self.completed_tasks, int):
            raise CoreTypeException("completed_tasks deve ser um inteiro")
            
        if not isinstance(self.failed_tasks, int):
            raise CoreTypeException("failed_tasks deve ser um inteiro")
            
        if not isinstance(self.retry_tasks, int):
            raise CoreTypeException("retry_tasks deve ser um inteiro")
        
        if not isinstance(self.avg_processing_time, (int, float)):
            raise CoreTypeException("avg_processing_time deve ser um número")
        
        logger.debug(f"Estatísticas para fila '{self.queue_name}' criadas")
    
    @property
    def total_tasks(self) -> int:
        """Retorna o número total de tarefas já processadas ou em processamento.
        
        Returns:
            int: Total de tarefas.
        """
        return self.pending_tasks + self.in_progress_tasks + self.completed_tasks + self.failed_tasks + self.retry_tasks
    
    @property
    def success_rate(self) -> float:
        """Calcula a taxa de sucesso das tarefas processadas.
        
        Returns:
            float: Taxa de sucesso (0.0 a 1.0).
        """
        processed = self.completed_tasks + self.failed_tasks
        if processed == 0:
            return 1.0
        return self.completed_tasks / processed

# -----------------------------------------------------------------------------
# Tipos para gerenciamento de filas
# -----------------------------------------------------------------------------

@dataclass
class QueueProcessor(BaseModel):
    """Processador de uma fila.
    
    Define o comportamento para processamento de tarefas em uma fila,
    incluindo callbacks para processamento e tratamento de erros.
    
    Attributes:
        queue_name (str): Nome da fila a ser processada.
        processor_func (Callable[[QueueableTask], QueueableTask]): Função que processa uma tarefa da fila.
        error_handler (Optional[Callable[[Exception, QueueableTask], None]]): Função para tratamento de erros (opcional).
        config (QueueConfig): Configurações da fila.
        stats (QueueStats): Estatísticas da fila.
    """
    queue_name: str
    processor_func: Callable[[QueueableTask], QueueableTask]
    error_handler: Optional[Callable[[Exception, QueueableTask], None]] = None
    config: QueueConfig = field(default_factory=lambda: QueueConfig(name="default"))
    stats: QueueStats = field(default_factory=lambda: QueueStats(queue_name="default"))
    
    def __post_init__(self):
        """Inicializa valores padrão se necessário."""
        if not isinstance(self.queue_name, str):
            raise ValueError("queue_name deve ser uma string")
        
        if not callable(self.processor_func):
            raise ValueError("processor_func deve ser uma função chamável")
            
        if self.error_handler is not None and not callable(self.error_handler):
            raise ValueError("error_handler deve ser uma função chamável")
            
        if not isinstance(self.config, QueueConfig):
            raise ValueError("config deve ser uma instância de QueueConfig")
            
        if not isinstance(self.stats, QueueStats):
            raise ValueError("stats deve ser uma instância de QueueStats")
            
        logger.info(f"QueueProcessor criado para fila '{self.queue_name}'")
    
    def process(self, task: QueueableTask) -> QueueableTask:
        """Processa uma tarefa da fila.
        
        Args:
            task (QueueableTask): Tarefa a ser processada.
            
        Returns:
            QueueableTask: A tarefa processada (atualizada).
        """
        logger.info(f"Processando tarefa {task.task_id} na fila '{self.queue_name}'")
        
        # Atualiza estatísticas
        self.stats.in_progress_tasks += 1
        
        try:
            # Processa a tarefa e obtém a versão atualizada
            updated_task = self.processor_func(task)
            
            # Atualiza estatísticas após processamento
            self.stats.in_progress_tasks -= 1
            
            # Se a tarefa foi concluída com sucesso
            if updated_task.status == EntityStatus.COMPLETED:
                self.stats.completed_tasks += 1
            elif updated_task.status == EntityStatus.FAILED:
                self.stats.failed_tasks += 1
            
            return updated_task
            
        except Exception as e:
            # Atualiza estatísticas após falha
            self.stats.in_progress_tasks -= 1
            self.stats.failed_tasks += 1
            
            logger.error(f"Erro ao processar tarefa {task.task_id}: {str(e)}", exc_info=True)
            
            # Marca a tarefa como falha
            task.set_failure(str(e))
            
            # Chama o handler de erro se existir
            if self.error_handler:
                try:
                    self.error_handler(e, task)
                except Exception as handler_error:
                    logger.error(f"Erro no error_handler: {str(handler_error)}", exc_info=True)
            
            return task

