"""
Tipos para gerenciamento de filas e tarefas assíncronas.

Define estruturas de dados para representar tarefas executáveis
em background e configurações de filas de processamento.
"""
import logging
from typing import Callable, List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from .base import Result
from .task import TaskBase, QueueableTask, QueueableTaskCollection, QueueConfig
from core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para gerenciamento de filas
# -----------------------------------------------------------------------------
@dataclass
class QueueStats:
    """Estatísticas de uma fila de processamento.
    
    Armazena métricas e informações sobre o estado atual
    e histórico de processamento de uma fila.
    
    Args:
        queue_name: Nome da fila.
        pending_tasks: Número de tarefas aguardando processamento.
        in_progress_tasks: Número de tarefas em processamento.
        completed_tasks: Número de tarefas concluídas com sucesso.
        failed_tasks: Número de tarefas que falharam.
        retry_tasks: Número de tarefas aguardando nova tentativa.
        avg_processing_time: Tempo médio de processamento em segundos.
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte as estatísticas para um dicionário.
        
        Returns:
            Dict: Dicionário com as estatísticas.
        """
        return {
            "queue_name": self.queue_name,
            "pending_tasks": self.pending_tasks,
            "in_progress_tasks": self.in_progress_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "retry_tasks": self.retry_tasks,
            "avg_processing_time": self.avg_processing_time,
            "total_tasks": self.total_tasks,
            "success_rate": self.success_rate
        }

@dataclass
class QueueProcessor:
    """Processador de uma fila.
    
    Define o comportamento para processamento de tarefas em uma fila,
    incluindo callbacks para processamento e tratamento de erros.
    
    Args:
        queue_name: Nome da fila a ser processada.
        processor_func: Função que processa uma tarefa da fila.
        error_handler: Função para tratamento de erros (opcional).
        config: Configurações da fila.
        stats: Estatísticas da fila.
    """
    queue_name: str
    processor_func: Callable[[QueueableTask], Result[Any]]
    error_handler: Optional[Callable[[Exception, QueueableTask], None]] = None
    config: QueueConfig = None
    stats: QueueStats = None
    
    def __post_init__(self):
        """Inicializa valores padrão se necessário."""
        if not callable(self.processor_func):
            raise ValueError("processor_func deve ser uma função chamável")
            
        if self.error_handler is not None and not callable(self.error_handler):
            raise ValueError("error_handler deve ser uma função chamável")
            
        if self.config is None:
            self.config = QueueConfig(name=self.queue_name)
            
        if self.stats is None:
            self.stats = QueueStats(queue_name=self.queue_name)
            
        logger.info(f"QueueProcessor criado para fila '{self.queue_name}'")
    
    def process(self, task: QueueableTask) -> Result[Any]:
        """Processa uma tarefa da fila.
        
        Args:
            task: Tarefa a ser processada.
            
        Returns:
            Result: Resultado da operação.
        """
        logger.info(f"Processando tarefa {task.task_id} na fila '{self.queue_name}'")
        
        # Atualiza estatísticas
        self.stats.in_progress_tasks += 1
        
        try:
            result = self.processor_func(task)
            
            # Atualiza estatísticas após processamento
            self.stats.in_progress_tasks -= 1
            self.stats.completed_tasks += 1
            
            return result
            
        except Exception as e:
            # Atualiza estatísticas após falha
            self.stats.in_progress_tasks -= 1
            self.stats.failed_tasks += 1
            
            logger.error(f"Erro ao processar tarefa {task.task_id}: {str(e)}", exc_info=True)
            
            # Chama o handler de erro se existir
            if self.error_handler:
                try:
                    self.error_handler(e, task)
                except Exception as handler_error:
                    logger.error(f"Erro no error_handler: {str(handler_error)}", exc_info=True)
            
            return Result.failure(str(e))