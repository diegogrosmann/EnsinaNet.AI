"""Gerenciador de filas de tarefas assíncronas."""

import logging
import time
import random
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List

from core.types import QueueableTask, QueueConfig, QueueableTaskCollection

logger = logging.getLogger(__name__)

class TaskQueue:
    """Fila de tarefas com parâmetros configuráveis."""
    
    def __init__(self, config: QueueConfig):
        self.name: str = config.name
        self.config: QueueConfig = config
        self.tasks: QueueableTaskCollection = []
        
        # Configura semáforos para controle de concorrência
        first_limit = (sys.maxsize if config.max_parallel_first == -1 
                      else config.max_parallel_first)
        retry_limit = (sys.maxsize if config.max_parallel_retry == -1 
                      else config.max_parallel_retry)
                      
        self.first_semaphore = threading.Semaphore(first_limit)
        self.retry_semaphore = threading.Semaphore(retry_limit)
        
        logger.info(f"Fila '{self.name}' criada com max_attempts={config.max_attempts}")

    def add_task(self, task: QueueableTask) -> None:
        """Adiciona uma tarefa à fila."""
        logger.debug(f"Fila '{self.config.name}': Tarefa '{task.identifier}' adicionada")
        self.tasks.append(task)

    def _run_task(self, task: QueueableTask) -> Any:
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
