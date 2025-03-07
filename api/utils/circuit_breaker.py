"""
Módulo responsável por implementar um circuit breaker básico em memória.

Este módulo controla falhas sucessivas ao chamar serviços externos de IA,
evitando chamadas desnecessárias quando um serviço está indisponível.

Classes:
    CircuitOpenError: Exceção levantada quando o circuito está aberto.
Funções:
    attempt_call(client_name: str):
        Verifica se o circuito está aberto para o cliente. Lança CircuitOpenError se estiver.
    record_failure(client_name: str):
        Registra falha. Abre circuito se ultrapassar limite configurado.
    record_success(client_name: str):
        Registra sucesso. Se estiver half_open, fecha o circuito.
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Estado do circuit breaker para cada API
circuit_state: Dict[str, Dict[str, Any]] = {}
locks: Dict[str, threading.RLock] = {}

# Configuração padrão
DEFAULT_ERROR_THRESHOLD = 100  # Reduzido para 5 para ser mais sensível a falhas
DEFAULT_TIMEOUT_SECONDS = 30  # Reduzido para 30s para permitir que APIs se recuperem mais rápido
DEFAULT_SUCCESS_THRESHOLD = 1  # Reduzido para 1 para permitir recuperação mais rápida

class CircuitOpenError(Exception):
    """Erro levantado quando o circuito está aberto."""
    pass

def get_or_create_state(api_name: str) -> Dict[str, Any]:
    """
    Recupera ou cria o estado do circuit breaker para uma API.
    
    Args:
        api_name (str): Nome identificador da API
        
    Returns:
        Dict[str, Any]: Estado atual do circuito para a API
    """
    if api_name not in circuit_state:
        circuit_state[api_name] = {
            'state': 'closed',  # closed, open, half-open
            'failures': 0,
            'successes': 0,
            'last_failure': None,
            'reset_timeout': DEFAULT_TIMEOUT_SECONDS,
            'error_threshold': DEFAULT_ERROR_THRESHOLD,
            'success_threshold': DEFAULT_SUCCESS_THRESHOLD
        }
        locks[api_name] = threading.RLock()
    
    return circuit_state[api_name]

def attempt_call(api_name: str) -> None:
    """
    Verifica se é possível realizar uma chamada para a API.
    
    Args:
        api_name (str): Nome identificador da API
        
    Raises:
        CircuitOpenError: Se o circuito estiver aberto
    """
    with locks.get(api_name, threading.RLock()):
        state = get_or_create_state(api_name)
        
        # Se o circuito estiver aberto
        if state['state'] == 'open':
            # Verifica se o tempo de timeout foi alcançado
            if (state['last_failure'] + timedelta(seconds=state['reset_timeout']) < datetime.now()):
                logger.info(f"Circuito para {api_name} mudou para meio-aberto após timeout")
                state['state'] = 'half-open'
                state['successes'] = 0
            else:
                # Circuito ainda está aberto
                raise CircuitOpenError(f"Circuito para {api_name} está aberto. Tente novamente mais tarde.")

def record_success(api_name: str) -> None:
    """
    Registra uma chamada bem-sucedida.
    
    Args:
        api_name (str): Nome identificador da API
    """
    with locks.get(api_name, threading.RLock()):
        state = get_or_create_state(api_name)
        
        # Reseta contador de falhas
        state['failures'] = 0
        
        # Se o circuito estiver meio-aberto, incrementa sucessos
        if state['state'] == 'half-open':
            state['successes'] += 1
            
            # Se atingiu o limiar de sucessos, fecha o circuito
            if state['successes'] >= state['success_threshold']:
                logger.info(f"Circuito para {api_name} fechado após {state['successes']} sucessos")
                state['state'] = 'closed'
                state['successes'] = 0

def record_failure(api_name: str) -> None:
    """
    Registra uma falha na chamada à API.
    
    Args:
        api_name (str): Nome identificador da API
    """
    with locks.get(api_name, threading.RLock()):
        state = get_or_create_state(api_name)
        state['failures'] += 1
        state['last_failure'] = datetime.now()
        
        # Se está no estado meio-aberto, qualquer falha já abre o circuito novamente
        if state['state'] == 'half-open':
            logger.info(f"Circuito para {api_name} reaberto após falha no estado meio-aberto")
            state['state'] = 'open'
            state['failures'] = state['error_threshold']  # força o estado aberto
            return
            
        # Se atingiu o limiar de erros, abre o circuito
        if state['failures'] >= state['error_threshold'] and state['state'] == 'closed':
            logger.warning(f"Circuito para {api_name} aberto após {state['failures']} falhas consecutivas")
            state['state'] = 'open'
