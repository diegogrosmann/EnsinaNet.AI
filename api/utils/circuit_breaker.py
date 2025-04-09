"""Circuit breaker para controle de falhas em chamadas de API.

Implementa o padrão Circuit Breaker para proteger o sistema contra falhas
em cascata quando serviços externos apresentam problemas, permitindo
degradação controlada e recuperação automática.
"""

import logging
import threading
from typing import Dict, Any, Optional

from api.exceptions import CircuitOpenException
from core.exceptions import AppException
from core.types.circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker
)

logger = logging.getLogger(__name__)

# Instância global para uso em toda a aplicação
_circuit_breaker_manager = {}
_circuit_breaker_lock = threading.RLock()

def get_circuit_breaker(api_name: str) -> CircuitBreaker:
    """Obtém ou cria um circuit breaker para uma API específica.
    
    Args:
        api_name: Nome da API para identificação do circuit breaker.
        
    Returns:
        CircuitBreaker: Instância configurada para a API.
    """
    with _circuit_breaker_lock:
        if api_name not in _circuit_breaker_manager:
            config = CircuitBreakerConfig(service_name=api_name)
            _circuit_breaker_manager[api_name] = CircuitBreaker(config=config)
        
        return _circuit_breaker_manager[api_name]

def attempt_call(api_name: str) -> None:
    """Verifica se uma chamada pode ser realizada para a API.
    
    Esta função deve ser chamada antes de qualquer tentativa de 
    comunicação com um serviço externo para verificar se o
    circuit breaker permite a chamada.
    
    Args:
        api_name: Nome da API a ser verificada.
        
    Raises:
        CircuitOpenError: Se o circuit breaker estiver aberto.
    """
    circuit_breaker = get_circuit_breaker(api_name)
    metrics = circuit_breaker.metrics
    
    if not metrics.should_allow_request(circuit_breaker.config):
        metrics.record_rejection()
        raise CircuitOpenException(f"Circuit breaker aberto para {api_name}")
        
    logger.debug(f"Tentativa de chamada permitida para: {api_name}")

def record_success(api_name: str) -> None:
    """Registra sucesso na chamada para uma API.
    
    Deve ser chamada após uma comunicação bem-sucedida com um serviço externo.
    
    Args:
        api_name: Nome da API que teve a chamada bem-sucedida.
    """
    logger.debug(f"Registrando sucesso para API: {api_name}")
    circuit_breaker = get_circuit_breaker(api_name)
    circuit_breaker.on_success()

def record_failure(api_name: str) -> None:
    """Registra falha na chamada para uma API.
    
    Deve ser chamada quando uma comunicação com um serviço externo falha.
    
    Args:
        api_name: Nome da API que teve a chamada com falha.
    """
    logger.debug(f"Registrando falha para API: {api_name}")
    circuit_breaker = get_circuit_breaker(api_name)
    circuit_breaker.on_failure()

def get_status(api_name: Optional[str] = None) -> Dict[str, Any]:
    """Retorna o status atual do circuit breaker para uma ou todas as APIs.
    
    Args:
        api_name: Nome da API específica (opcional, retorna todas se não especificado).
        
    Returns:
        Dict com informações de status do circuit breaker.
    """
    if api_name:
        if api_name in _circuit_breaker_manager:
            return {api_name: _circuit_breaker_manager[api_name].metrics.get_summary()}
        return {}
    
    # Retorna status de todos os circuit breakers
    result = {}
    for name, breaker in _circuit_breaker_manager.items():
        result[name] = breaker.metrics.get_summary()
    
    return result

def reset_breaker(api_name: str) -> None:
    """Reseta o circuit breaker para uma API específica.
    
    Força o estado do circuit breaker para CLOSED, ignorando
    o histórico de falhas (uso geralmente apenas para testes).
    
    Args:
        api_name: Nome da API a ser resetada.
        
    Raises:
        ApplicationError: Se ocorrer erro ao resetar o circuit breaker.
    """
    try:
        if api_name in _circuit_breaker_manager:
            circuit_breaker = _circuit_breaker_manager[api_name]
            circuit_breaker.metrics.change_state(CircuitState.CLOSED)
            circuit_breaker.metrics.reset_counters()
            logger.info(f"Circuit breaker para {api_name} foi resetado manualmente")
        else:
            logger.warning(f"Tentativa de resetar circuit breaker inexistente: {api_name}")
    except Exception as e:
        logger.error(f"Erro ao resetar circuit breaker para {api_name}: {str(e)}")
        raise AppException(f"Erro ao resetar circuit breaker: {str(e)}")
