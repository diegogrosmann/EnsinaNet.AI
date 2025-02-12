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

import time
import threading
import logging  # Adicionado import do logging

# Configuração do logger
logger = logging.getLogger(__name__)

class CircuitOpenError(Exception):
    """Exceção lançada quando o circuito está aberto para determinado cliente."""
    pass

# (NOVO) Dicionário global que mantém o estado do circuito para cada cliente de IA:
# Exemplo de estrutura:
# CIRCUIT_STATE[client_name] = {
#     "state": "closed"/"open"/"half_open",
#     "failure_count": int,
#     "opened_at": float,  # timestamp em que o circuito foi aberto
# }
CIRCUIT_STATE = {}
CIRCUIT_LOCK = threading.Lock()

# (NOVO) Configurações simples do circuito
FAILURE_THRESHOLD = 3   # Número máximo de falhas para "abrir" o circuito
OPEN_SECONDS = 30       # Tempo (segundos) que o circuito permanece aberto antes de 'half_open'

def attempt_call(client_name: str):
    """Verifica se é possível chamar o cliente de IA.

    Args:
        client_name (str): Nome do cliente de IA.

    Raises:
        CircuitOpenError: Se o circuito estiver aberto ou não puder prosseguir.
    """
    with CIRCUIT_LOCK:
        if client_name not in CIRCUIT_STATE:
            CIRCUIT_STATE[client_name] = {
                "state": "closed",
                "failure_count": 0,
                "opened_at": 0
            }
            return

        state = CIRCUIT_STATE[client_name]
        
        # Se estiver aberto, verifica timeout
        if state["state"] == "open":
            if time.time() - state["opened_at"] > OPEN_SECONDS:
                state["state"] = "half_open"
                logger.info(f"Circuito em half-open para {client_name}")
            else:
                raise CircuitOpenError(f"Circuito aberto para {client_name}")

def record_failure(client_name: str):
    """Registra uma falha na chamada do cliente de IA.

    Args:
        client_name (str): Nome do cliente de IA.
    """
    with CIRCUIT_LOCK:
        if client_name not in CIRCUIT_STATE:
            CIRCUIT_STATE[client_name] = {
                "state": "closed",
                "failure_count": 0,
                "opened_at": 0
            }
        
        state = CIRCUIT_STATE[client_name]
        state["failure_count"] += 1

        if state["failure_count"] >= FAILURE_THRESHOLD:
            state["state"] = "open"
            state["opened_at"] = time.time()
            logger.warning(f"Circuito aberto para {client_name} após {state['failure_count']} falhas")

def record_success(client_name: str):
    """Registra sucesso na chamada do cliente de IA.

    Args:
        client_name (str): Nome do cliente de IA.
    """
    with CIRCUIT_LOCK:
        if client_name not in CIRCUIT_STATE:
            return
            
        state = CIRCUIT_STATE[client_name]
        
        if state["state"] == "half_open":
            state["state"] = "closed"
            state["failure_count"] = 0
            logger.info(f"Circuito fechado para {client_name} após sucesso")
