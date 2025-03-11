"""Gerenciador de filas de tarefas assíncronas.

Implementa um sistema de filas para processamento assíncrono de tarefas,
com suporte a retentativas, backoff exponencial e limitação de concorrência.
"""

import logging
import time
import random
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Representa uma tarefa a ser executada.
    
    Attributes:
        identifier: Identificador único da tarefa.
        func: Função a ser executada.
        args: Argumentos posicionais.
        kwargs: Argumentos nomeados.
        result_callback: Callback para processar resultado.
        attempt: Número da tentativa atual.
    """
    identifier: str
    func: Callable
    args: tuple = ()
    kwargs: Dict = None
    result_callback: Optional[Callable[[str, Any], None]] = None
    attempt: int = 1

@dataclass
class QueueConfig:
    """Configuração de uma fila de tarefas.
    
    Attributes:
        max_attempts: Máximo de tentativas por tarefa.
        initial_wait: Tempo inicial entre tentativas.
        backoff_factor: Fator de multiplicação do tempo de espera.
        randomness_factor: Fator de aleatoriedade no tempo de espera.
        max_parallel_first: Máximo de execuções paralelas na primeira tentativa.
        max_parallel_retry: Máximo de execuções paralelas nas retentativas.
    """
    max_attempts: int
    initial_wait: float
    backoff_factor: float
    randomness_factor: float
    max_parallel_first: int
    max_parallel_retry: int

class TaskQueue:
    """Fila de tarefas com parâmetros configuráveis.
    
    Attributes:
        name: Nome identificador da fila.
        config: Configurações da fila.
        tasks: Lista de tarefas pendentes.
        first_semaphore: Controle de concorrência para primeira tentativa.
        retry_semaphore: Controle de concorrência para retentativas.
    """
    
    def __init__(self, name: str, config: QueueConfig):
        self.name = name
        self.config = config
        self.tasks: List[Task] = []
        
        # Configura semáforos para controle de concorrência
        first_limit = (sys.maxsize if config.max_parallel_first == -1 
                      else config.max_parallel_first)
        retry_limit = (sys.maxsize if config.max_parallel_retry == -1 
                      else config.max_parallel_retry)
                      
        self.first_semaphore = threading.Semaphore(first_limit)
        self.retry_semaphore = threading.Semaphore(retry_limit)
        
        logger.info(f"Fila '{name}' criada com max_attempts={config.max_attempts}")

    def add_task(self, task: Task) -> None:
        """Adiciona uma tarefa à fila."""
        logger.debug(f"Fila '{self.name}': Tarefa '{task.identifier}' adicionada")
        self.tasks.append(task)

    def _run_task(self, task: Task) -> Any:
        """Executa uma tarefa com retentativas.
        
        Args:
            task: Tarefa a ser executada.
            
        Returns:
            Any: Resultado da execução ou None se falhar.
        """
        while task.attempt <= self.config.max_attempts:
            semaphore = (self.first_semaphore if task.attempt == 1 
                        else self.retry_semaphore)
            
            with semaphore:
                try:
                    start_time = time.time()
                    result = task.func(*task.args, **(task.kwargs or {}))
                    elapsed = time.time() - start_time
                    
                    if task.result_callback:
                        task.result_callback(task.identifier, result)
                        
                    logger.info(
                        f"Fila '{self.name}': Tarefa '{task.identifier}' "
                        f"concluída na tentativa {task.attempt} em {elapsed:.2f}s"
                    )
                    return result
                    
                except Exception as e:
                    elapsed = time.time() - start_time
                    logger.exception(
                        f"Fila '{self.name}': Erro na tarefa '{task.identifier}' "
                        f"(tentativa {task.attempt}/{self.config.max_attempts}): {e}"
                    )
                    
                    if task.attempt == self.config.max_attempts:
                        if task.result_callback:
                            task.result_callback(task.identifier, {"error": str(e)})
                        return None
                    
                    delay = self._calculate_delay(task.attempt)
                    logger.info(f"Aguardando {delay:.2f}s para nova tentativa")
                    time.sleep(delay)
                    task.attempt += 1

    def _calculate_delay(self, attempt: int) -> float:
        """Calcula o tempo de espera entre tentativas.
        
        Args:
            attempt: Número da tentativa atual.
            
        Returns:
            float: Tempo de espera em segundos.
        """
        delay = self.config.initial_wait * (self.config.backoff_factor ** (attempt - 1))
        random_factor = random.uniform(
            1 - self.config.randomness_factor,
            1 + self.config.randomness_factor
        )
        return delay * random_factor

    def process_tasks(self) -> None:
        """Processa todas as tarefas da fila em paralelo."""
        tasks_count = len(self.tasks)
        logger.info(f"Fila '{self.name}': Processando {tasks_count} tarefas")
        
        start_time = time.time()
        
        # Configura o pool de threads
        max_workers = max(
            self.config.max_parallel_first,
            self.config.max_parallel_retry
        )
        if max_workers == -1:
            max_workers = min(32, (tasks_count + 4))
            
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._run_task, task) for task in self.tasks]
            for future in futures:
                future.result()
                
        elapsed = time.time() - start_time
        logger.info(
            f"Fila '{self.name}': {tasks_count} tarefas processadas em {elapsed:.2f}s"
        )

class TaskManager:
    """
    Gerencia uma ou mais filas de tasks, processando-as em paralelo.
    """
    def __init__(self):
        self.queues = []

    def add_queue(self, queue: TaskQueue) -> None:
        logger.debug(f"TaskManager: Adicionada fila '{queue.name}' com {len(queue.tasks)} tarefas")
        self.queues.append(queue)

    def run(self) -> None:
        queues_count = len(self.queues)
        logger.info(f"TaskManager: Iniciando processamento de {queues_count} filas")
        start_time = time.time()
        
        threads = []
        for queue in self.queues:
            logger.debug(f"TaskManager: Iniciando thread para fila '{queue.name}'")
            t = threading.Thread(target=queue.process_tasks)
            t.start()
            threads.append(t)
        
        for t in threads:
            t.join()
        
        elapsed_time = time.time() - start_time
        logger.info(f"TaskManager: Processamento de todas as {queues_count} filas concluído em {elapsed_time:.2f}s")
