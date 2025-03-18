"""
Tipos relacionados ao padrão Circuit Breaker para resiliência de sistemas.
"""
from typing import Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# -----------------------------------------------------------------------------
# Tipos para Circuit Breaker
# -----------------------------------------------------------------------------
class CircuitState(Enum):
    """Estados possíveis do Circuit Breaker.
    
    O Circuit Breaker é um padrão de design utilizado para detectar falhas e 
    encapsular a lógica de prevenção de falhas em cascata em sistemas distribuídos.
    
    Valores:
        CLOSED: Estado normal de operação, requisições processadas normalmente.
        OPEN: Estado de falha, requisições são rejeitadas imediatamente.
        HALF_OPEN: Estado de teste limitado para verificar recuperação do sistema.
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker.
    
    Args:
        failure_threshold: Número de falhas para abrir o circuito.
        reset_timeout: Tempo aberto antes de half-open (segundos).
        half_open_timeout: Tempo máximo em half-open (segundos).
        success_threshold: Sucessos necessários para fechar o circuito.
        excluded_exceptions: Exceções ignoradas pelo circuit breaker.
    """
    failure_threshold: int = 5
    reset_timeout: float = 60.0
    half_open_timeout: float = 30.0
    success_threshold: int = 2
    excluded_exceptions: Set[Exception] = field(default_factory=set)

@dataclass
class CircuitBreakerMetrics:
    """Métricas do Circuit Breaker.
    
    Args:
        failure_count: Contador de falhas.
        success_count: Contador de sucessos.
        last_failure_time: Momento da última falha.
        last_success_time: Momento do último sucesso.
        state: Estado atual do circuito.
    """
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED
