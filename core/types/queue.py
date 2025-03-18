"""
Tipos para gerenciamento de filas e tarefas assíncronas.
"""
from typing import Callable, List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

# -----------------------------------------------------------------------------
# Tipos para queue e fila de tarefas
# -----------------------------------------------------------------------------
@dataclass
class QueueableTask:
    """Representa uma tarefa a ser executada.
    
    Args:
        identifier: Identificador da tarefa.
        func: Função a ser executada.
        args: Argumentos posicionais.
        kwargs: Argumentos nomeados.
        result_callback: Callback de resultado.
        attempt: Número de tentativas.
    """
    identifier: str
    func: Callable
    args: tuple = ()
    kwargs: Dict = field(default_factory=dict)
    result_callback: Optional[Callable[[str, Any], None]] = None
    attempt: int = 1

QueueableTaskCollection = List[QueueableTask]

@dataclass
class QueueConfig:
    """Configuração da fila de tarefas.
    
    Args:
        name: Nome da fila.
        max_attempts: Máximo de tentativas.
        initial_wait: Intervalo inicial entre tentativas (segundos).
        backoff_factor: Fator de aumento de espera entre tentativas.
        randomness_factor: Fator de aleatoriedade para evitar colisões.
        max_parallel_first: Máximo de tarefas em paralelo para primeira tentativa (-1 = ilimitado).
        max_parallel_retry: Máximo de tarefas em paralelo para retentativas.
        timeout: Tempo máximo de execução de uma tarefa (segundos).
    """
    name: str
    max_attempts: int = 3
    initial_wait: float = 30
    backoff_factor: float = 2
    randomness_factor: float = 0.2
    max_parallel_first: int = -1
    max_parallel_retry: int = 1
    timeout: float = 300.0
