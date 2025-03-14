"""Circuit breaker para controle de falhas em chamadas de API."""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.exceptions import CircuitOpenError
from core.types import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerMetrics
)

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Implementa o padrão Circuit Breaker para proteção de APIs."""
    
    def __init__(self, config: CircuitBreakerConfig) -> None:
        self.config = config
        self.metrics: Dict[str, CircuitBreakerMetrics] = {}
        self._lock = threading.Lock()
        
    def _get_metrics(self, api_name: str) -> CircuitBreakerMetrics:
        """Retorna ou cria métricas para uma API."""
        with self._lock:
            if api_name not in self.metrics:
                self.metrics[api_name] = CircuitBreakerMetrics()
            return self.metrics[api_name]
            
    def can_execute(self, api_name: str) -> bool:
        """Verifica se uma chamada pode ser executada."""
        metrics = self._get_metrics(api_name)
        
        if metrics.state == CircuitState.CLOSED:
            return True
            
        if metrics.state == CircuitState.OPEN:
            if datetime.now() - (metrics.last_failure_time or datetime.now()) > timedelta(seconds=self.config.reset_timeout):
                metrics.state = CircuitState.HALF_OPEN
                return True
            return False
            
        # Estado HALF_OPEN
        return True

    def record_success(self, api_name: str) -> None:
        """Registra uma chamada bem sucedida."""
        metrics = self._get_metrics(api_name)
        with self._lock:
            metrics.success_count += 1
            metrics.last_success_time = datetime.now()
            
            if metrics.state == CircuitState.HALF_OPEN and metrics.success_count >= self.config.success_threshold:
                metrics.state = CircuitState.CLOSED
                metrics.failure_count = 0
                metrics.success_count = 0

    def record_failure(self, api_name: str) -> None:
        """Registra uma falha na chamada."""
        metrics = self._get_metrics(api_name)
        with self._lock:
            metrics.failure_count += 1
            metrics.last_failure_time = datetime.now()
            
            if metrics.state == CircuitState.HALF_OPEN or metrics.failure_count >= self.config.failure_threshold:
                metrics.state = CircuitState.OPEN
                metrics.failure_count = 0
                metrics.success_count = 0

# Instância global
_circuit_breaker = CircuitBreaker(CircuitBreakerConfig())

def attempt_call(api_name: str) -> None:
    """Verifica se uma chamada pode ser realizada."""
    if not _circuit_breaker.can_execute(api_name):
        raise CircuitOpenError(f"Circuit breaker aberto para {api_name}")

def record_success(api_name: str) -> None:
    """Registra sucesso na chamada."""
    _circuit_breaker.record_success(api_name)

def record_failure(api_name: str) -> None:
    """Registra falha na chamada."""
    _circuit_breaker.record_failure(api_name)
