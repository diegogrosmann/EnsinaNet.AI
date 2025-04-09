"""
Modelo unificado para status em toda a aplicação.

Define uma estrutura comum para representar estados de entidades do sistema,
incluindo tarefas, operações, processos e outros objetos com ciclo de vida.
"""
import logging
from typing import Dict, Any, Set

from core.types.base import BaseEnum

logger = logging.getLogger(__name__)


class EntityStatus(BaseEnum):
    """Códigos de status unificados para toda a aplicação.
    
    Define todos os possíveis estados em que uma entidade do sistema pode estar,
    servindo como vocabulário padronizado para representar status em toda a aplicação.
    
    Values:
        NOT_STARTED: Entidade criada, mas processamento ainda não iniciado.
        PENDING: Entidade aguardando processamento na fila.
        IN_PROGRESS: Entidade sendo processada ativamente.
        PROCESSING: Alternativa para IN_PROGRESS, usada em alguns contextos.
        WAITING: Entidade aguardando outro evento ou condição.
        PAUSED: Processamento temporariamente pausado.
        COMPLETED: Processamento concluído com sucesso.
        FAILED: Processamento falhou com erro.
        EXPIRED: Entidade expirou sem processamento completo.
        CANCELLED: Processamento cancelado pelo usuário ou sistema.
        TIMEOUT: Processamento interrompido por tempo limite.
        PARTIALLY_COMPLETED: Processamento concluído apenas parcialmente.
    """
    NOT_STARTED = "not_started"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PARTIALLY_COMPLETED = "partially_completed"
    

    
    @classmethod
    def terminal_statuses(cls) -> Set['EntityStatus']:
        """Retorna o conjunto de status considerados terminais (finais)."""
        return {cls.COMPLETED, cls.FAILED, cls.EXPIRED, cls.CANCELLED, cls.TIMEOUT, cls.PARTIALLY_COMPLETED}
    
    @classmethod
    def error_statuses(cls) -> Set['EntityStatus']:
        """Retorna o conjunto de status que indicam erro."""
        return {cls.FAILED, cls.EXPIRED, cls.TIMEOUT}
    
    @classmethod
    def active_statuses(cls) -> Set['EntityStatus']:
        """Retorna o conjunto de status que indicam processamento ativo."""
        return {cls.IN_PROGRESS, cls.PROCESSING}
    
    @property
    def is_terminal(self) -> bool:
        """Verifica se este é um status terminal (final).
        
        Returns:
            bool: True se o status for terminal, False caso contrário.
        """
        return self in self.__class__.terminal_statuses()
    
    @property
    def is_success(self) -> bool:
        """Verifica se este é um status de sucesso.
        
        Returns:
            bool: True se o status indicar conclusão bem-sucedida.
        """
        return self == EntityStatus.COMPLETED
    
    @property
    def is_error(self) -> bool:
        """Verifica se este é um status de erro.
        
        Returns:
            bool: True se o status indicar erro.
        """
        return self in self.__class__.error_statuses()
    
    @property
    def is_active(self) -> bool:
        """Verifica se este é um status de processamento ativo.
        
        Returns:
            bool: True se o status indicar processamento em andamento.
        """
        return self in self.__class__.active_statuses()


