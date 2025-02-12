"""
Módulo responsável por implementar um circuit breaker básico em memória, 
de modo a controlar falhas sucessivas ao chamar serviços externos de IA.

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
    """
    Verifica se podemos chamar a IA ou se o circuito está aberto.
    Lança CircuitOpenError se o circuito ainda estiver aberto ou 
    se não for possível prosseguir.

    Args:
        client_name (str): Nome do cliente de IA (por ex. "OpenAi", "Gemini", etc.).
    """
    with CIRCUIT_LOCK:
        state = CIRCUIT_STATE.get(client_name, {
            "state": "closed",
            "failure_count": 0,
            "opened_at": 0.0
        })

        # Se o estado for 'open', checar se podemos migrar para 'half_open'
        if state["state"] == "open":
            elapsed = time.time() - state["opened_at"]
            if elapsed < OPEN_SECONDS:
                # Ainda dentro do período de 'open'
                raise CircuitOpenError(f"Circuito para {client_name} está aberto.")
            else:
                # Tenta mudar para half_open
                state["state"] = "half_open"
                CIRCUIT_STATE[client_name] = state
        # Se estiver 'closed' ou 'half_open', deixamos prosseguir.
        # Sem retorno = sucesso.

def record_failure(client_name: str):
    """
    Registra uma falha na chamada do cliente de IA.
    Se o número de falhas atingir ou exceder FAILURE_THRESHOLD,
    abre o circuito e marca o timestamp de abertura.

    Args:
        client_name (str): Nome do cliente de IA.
    """
    with CIRCUIT_LOCK:
        state = CIRCUIT_STATE.get(client_name, {
            "state": "closed",
            "failure_count": 0,
            "opened_at": 0.0
        })
        state["failure_count"] += 1

        # Se estava half_open, com 1 falha abrimos imediatamente
        # ou se estava closed e atingiu o threshold, abre também
        if state["state"] in ["half_open", "closed"]:
            if state["failure_count"] >= FAILURE_THRESHOLD:
                state["state"] = "open"
                state["opened_at"] = time.time()

        CIRCUIT_STATE[client_name] = state

def record_success(client_name: str):
    """
    Registra sucesso na chamada do cliente de IA.
    Se o circuito estiver em half_open, fecha (reseta contagem).
    Caso esteja closed, apenas zera contagem de falhas.

    Args:
        client_name (str): Nome do cliente de IA.
    """
    with CIRCUIT_LOCK:
        state = CIRCUIT_STATE.get(client_name, {
            "state": "closed",
            "failure_count": 0,
            "opened_at": 0.0
        })

        if state["state"] == "half_open":
            # Sucesso no modo half_open => volta a 'closed'
            state["state"] = "closed"
            state["failure_count"] = 0
        else:
            # Se está 'closed', apenas zera falhas
            if state["state"] == "closed":
                state["failure_count"] = 0

        CIRCUIT_STATE[client_name] = state
