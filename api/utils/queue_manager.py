import logging
import time
import random
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)

class Task:
    """
    Representa uma task que será executada.
    """
    def __init__(self, identifier: str, func: Callable, args: tuple = (), kwargs: dict = None,
                 result_callback: Callable[[str, Any], None] = None):
        self.identifier = identifier
        self.func = func
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        self.result_callback = result_callback
        self.attempt = 1  # Contador de tentativas

class TaskQueue:
    """
    Representa uma fila de tasks com parâmetros configuráveis.
    """
    def __init__(self, name: str, max_attempts: int, initial_wait: float, backoff_factor: float,
                 randomness_factor: float, max_parallel_first: int, max_parallel_retry: int):
        self.name = name
        self.max_attempts = max_attempts
        self.initial_wait = initial_wait
        self.backoff_factor = backoff_factor
        self.randomness_factor = randomness_factor
        self.max_parallel_first = max_parallel_first
        self.max_parallel_retry = max_parallel_retry
        self.tasks = []  # Lista de Task
        # Semáforos para limitar a concorrência das tasks
        # Usa valor muito alto (ilimitado na prática) quando valor for -1
        first_limit = sys.maxsize if max_parallel_first == -1 else max_parallel_first
        retry_limit = sys.maxsize if max_parallel_retry == -1 else max_parallel_retry
        self.first_semaphore = threading.Semaphore(first_limit)
        self.retry_semaphore = threading.Semaphore(retry_limit)
        logger.info(f"Fila '{name}' criada: max_attempts={max_attempts}, max_parallel_first={max_parallel_first} ({'ilimitado' if max_parallel_first == -1 else max_parallel_first}), max_parallel_retry={max_parallel_retry} ({'ilimitado' if max_parallel_retry == -1 else max_parallel_retry})")

    def add_task(self, task: Task) -> None:
        logger.debug(f"Fila '{self.name}': Tarefa '{task.identifier}' adicionada")
        self.tasks.append(task)

    def _run_task(self, task: Task) -> Any:
        """
        Executa a task com tratamento de retentativas e backoff exponencial.
        """
        while task.attempt <= self.max_attempts:
            # Seleciona o semáforo de acordo com a tentativa atual
            semaphore = self.first_semaphore if task.attempt == 1 else self.retry_semaphore
            with semaphore:
                logger.debug(f"Fila '{self.name}': Executando tarefa '{task.identifier}' (tentativa {task.attempt}/{self.max_attempts})")
                start_time = time.time()
                try:
                    result = task.func(*task.args, **task.kwargs)
                    elapsed_time = time.time() - start_time
                    if task.result_callback:
                        task.result_callback(task.identifier, result)
                    logger.info(f"Fila '{self.name}': Tarefa '{task.identifier}' concluída com sucesso na tentativa {task.attempt} em {elapsed_time:.2f}s")
                    return result
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    logger.exception(f"Fila '{self.name}': Erro na tarefa '{task.identifier}' na tentativa {task.attempt}/{self.max_attempts} após {elapsed_time:.2f}s: {e}")
                    if task.attempt == self.max_attempts:
                        logger.warning(f"Fila '{self.name}': Máximo de tentativas atingido para tarefa '{task.identifier}'")
                        if task.result_callback:
                            task.result_callback(task.identifier, {"error": str(e)})
                        return None
                
                    # Cálculo do delay com backoff exponencial e fator de aleatoriedade
                    delay = self.initial_wait * (self.backoff_factor ** (task.attempt - 1))
                    delay *= random.uniform(1 - self.randomness_factor, 1 + self.randomness_factor)
                    logger.info(f"Fila '{self.name}': Tarefa '{task.identifier}' aguardando {delay:.2f}s para nova tentativa")
                    # Mantém o semáforo bloqueado durante a espera para respeitar max_parallel_retry
                    time.sleep(delay)
                    task.attempt += 1

    def process_tasks(self) -> None:
        """
        Processa todas as tasks da fila em paralelo.
        """
        tasks_count = len(self.tasks)
        logger.info(f"Fila '{self.name}': Iniciando processamento de {tasks_count} tarefas")
        start_time = time.time()
        
        # Ajusta o número de workers quando configurado como ilimitado (-1)
        first_workers = sys.maxsize if self.max_parallel_first == -1 else self.max_parallel_first
        retry_workers = sys.maxsize if self.max_parallel_retry == -1 else self.max_parallel_retry
        max_workers = max(first_workers, retry_workers)
        # Para ThreadPoolExecutor, não podemos usar um valor tão grande, então definimos um limite razoável
        if max_workers == sys.maxsize:
            max_workers = min(32, (tasks_count + 4))  # Ajusta conforme número de tarefas com um limite razoável
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._run_task, task) for task in self.tasks]
            for future in futures:
                future.result()
        
        elapsed_time = time.time() - start_time
        logger.info(f"Fila '{self.name}': Processamento de {tasks_count} tarefas concluído em {elapsed_time:.2f}s")

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
