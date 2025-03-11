"""Circuit breaker para controle de falhas em chamadas de API."""

import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.types import CircuitState, CircuitConfig, CircuitOpenError

logger = logging.getLogger(__name__)

# Instância global do circuit breaker
_circuit_breaker = None  # Será inicializado posteriormente

class CircuitBreaker:
    """Implementação do padrão Circuit Breaker."""
    
    def __init__(self, config: Optional[CircuitConfig] = None):
        self._states: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, threading.RLock] = {}
        self._config = config or CircuitConfig()

    def _get_state(self, api_name: str) -> Dict[str, Any]:
        """Obtém ou cria estado para uma API."""
        if api_name not in self._states:
            self._states[api_name] = {
                'state': CircuitState.CLOSED,
                'failures': 0,
                'successes': 0,
                'last_failure': None
            }
            self._locks[api_name] = threading.RLock()
        return self._states[api_name]

    def attempt_call(self, api_name: str) -> None:
        """Verifica se é possível realizar uma chamada."""
        with self._locks.get(api_name, threading.RLock()):
            state = self._get_state(api_name)
            
            if state['state'] == CircuitState.OPEN:
                if (state['last_failure'] + 
                    timedelta(seconds=self._config.timeout_seconds) < datetime.now()):
                    logger.info(f"Circuito para {api_name} mudou para meio-aberto")
                    state['state'] = CircuitState.HALF_OPEN
                    state['successes'] = 0
                else:
                    raise CircuitOpenError(f"Circuito para {api_name} está aberto")

    def record_success(self, api_name: str) -> None:
        """Registra uma chamada bem-sucedida."""
        with self._locks.get(api_name, threading.RLock()):
            state = self._get_state(api_name)
            state['failures'] = 0
            
            if state['state'] == CircuitState.HALF_OPEN:
                state['successes'] += 1
                if state['successes'] >= self._config.success_threshold:
                    logger.info(f"Circuito para {api_name} fechado após {state['successes']} sucessos")
                    state['state'] = CircuitState.CLOSED
                    state['successes'] = 0

    def record_failure(self, api_name: str) -> None:
        """Registra uma falha na chamada."""
        with self._locks.get(api_name, threading.RLock()):
            state = self._get_state(api_name)
            state['failures'] += 1
            state['last_failure'] = datetime.now()
            
            if state['state'] == CircuitState.HALF_OPEN:
                logger.info(f"Circuito para {api_name} reaberto após falha")
                state['state'] = CircuitState.OPEN
                state['failures'] = self._config.error_threshold
                return
                
            if (state['failures'] >= self._config.error_threshold and 
                state['state'] == CircuitState.CLOSED):
                logger.warning(f"Circuito para {api_name} aberto após {state['failures']} falhas")
                state['state'] = CircuitState.OPEN

# Inicialização da instância global
_circuit_breaker = CircuitBreaker()

# APIs públicas
def attempt_call(api_name: str) -> None:
    """Wrapper para attempt_call do circuit breaker global."""
    _circuit_breaker.attempt_call(api_name)

def record_success(api_name: str) -> None:
    """Wrapper para record_success do circuit breaker global."""
    _circuit_breaker.record_success(api_name)

def record_failure(api_name: str) -> None:
    """Wrapper para record_failure do circuit breaker global."""
    _circuit_breaker.record_failure(api_name)
