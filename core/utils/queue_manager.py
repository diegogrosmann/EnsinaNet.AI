"""Gerenciador de filas de tarefas assíncronas.

Este módulo implementa um sistema de processamento de tarefas em segundo plano
com suporte a execução paralela e retentativas com backoff exponencial,
permitindo a execução eficiente de operações demoradas ou com alta taxa de falha.
"""

import logging
import time
import random
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List

from core.types import (
    QueueableTask, 
    QueueConfig, 
    QueueableTaskDict,
    QueueStats,
    EntityStatus
)

logger = logging.getLogger(__name__)

class TaskQueue:
    """Fila de tarefas com parâmetros configuráveis.
    
    Gerencia uma coleção de tarefas executáveis com suporte a retentativas
    e controle de concorrência por semáforos.
    
    Attributes:
        config: Configuração da fila.
        tasks: Lista de tarefas a serem executadas.
        retry_tasks: Lista de tarefas para retentativa.
        first_semaphore: Controle de concorrência para primeiras tentativas.
        retry_semaphore: Controle de concorrência para retentativas.
        stats: Estatísticas da fila.
    """
    
    def __init__(self, config: QueueConfig):
        """Inicializa a fila com a configuração fornecida.
        
        Args:
            config: Configuração com parâmetros da fila.
        """
        self.config = config
        self.tasks = []  # Lista simples para armazenar tarefas
        self.retry_tasks = []  # Lista simples para armazenar tarefas para retry
        
        # Semáforos para controle de concorrência
        max_parallel_first = config.max_parallel_first if config.max_parallel_first > 0 else sys.maxsize
        self.first_semaphore = threading.Semaphore(max_parallel_first)
        self.retry_semaphore = threading.Semaphore(config.max_parallel_retry)
        
        # Estatísticas
        self.stats = QueueStats(queue_name=config.name)
        
        logger.info(f"Fila '{config.name}' criada com {max_parallel_first} workers para primeiras tentativas"
                   f" e {config.max_parallel_retry} workers para retentativas")
    
    def add_task(self, task: QueueableTask) -> None:
        """Adiciona uma tarefa à fila.
        
        Args:
            task: Tarefa a ser adicionada.
        """
        self.tasks.append(task)
        self.stats.pending_tasks += 1
        logger.debug(f"Tarefa {task.task_id} adicionada à fila '{self.config.name}'")
    
    def _run_task(self, task: QueueableTask) -> QueueableTask:
        """Executa uma tarefa e gerencia retentativas se necessário.
        
        Args:
            task: Tarefa a ser executada.
            
        Returns:
            QueueableTask: Tarefa atualizada após execução.
        """
        # Atualizar estatísticas
        self.stats.pending_tasks -= 1
        self.stats.in_progress_tasks += 1
        
        start_time = time.time()
        
        # Executar a função da tarefa diretamente
        try:
            # Aqui faríamos o equivalente a executar a tarefa
            # Precisamos invocar a função da tarefa com seus argumentos e atualizar seu status
            result = task.func(*task.args, **task.kwargs)
            
            # Atualizar a tarefa com o resultado
            task.set_result(result)
        except Exception as e:
            # Em caso de exceção, marcar a tarefa como falha
            task.set_failure(str(e))
        
        elapsed_time = time.time() - start_time
        
        # Atualizar estatísticas após execução
        self.stats.in_progress_tasks -= 1
        
        if task.status == EntityStatus.COMPLETED:
            self.stats.completed_tasks += 1
            # Contribuir para o tempo médio de execução
            if self.stats.avg_processing_time == 0:
                self.stats.avg_processing_time = elapsed_time
            else:
                # Média móvel
                alpha = 0.2  # Peso para o novo valor
                self.stats.avg_processing_time = (alpha * elapsed_time) + ((1 - alpha) * self.stats.avg_processing_time)
                
            logger.debug(f"Tarefa {task.task_id} concluída com sucesso em {elapsed_time:.3f}s")
            return task
        
        # Falha na execução
        self.stats.failed_tasks += 1
        
        # Verificar se deve tentar novamente
        if self.config.should_retry(task.attempt, Exception(str(task.error))):
            # Calcular tempo de espera antes da próxima tentativa
            wait_time = self._calculate_delay(task.attempt)
            
            # Incrementar contador de tentativa
            task.attempt += 1
            
            # Adicionar à fila de retentativa
            self.retry_tasks.append(task)
            self.stats.retry_tasks += 1
            
            logger.warning(f"Tarefa {task.task_id} falhou (tentativa #{task.attempt-1}). "
                         f"Agendando nova tentativa em {wait_time:.1f}s")
            
            # Esperar antes da próxima tentativa
            time.sleep(wait_time)
        else:
            # Não tentar novamente, retornar erro
            logger.error(f"Tarefa {task.task_id} falhou permanentemente após {task.attempt} tentativas: {task.error}")
        
        return task
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calcula o tempo de espera antes da próxima tentativa.
        
        Args:
            attempt: Número da tentativa atual.
            
        Returns:
            Tempo de espera em segundos.
        """
        # Exponential backoff with jitter
        delay = self.config.calculate_wait_time(attempt)
        if delay <= 0:
            return 0
            
        # Adicionar aleatoriedade para evitar thundering herd
        jitter = random.uniform(-self.config.randomness_factor, self.config.randomness_factor)
        delay = delay * (1 + jitter)
        
        return max(0.1, delay)  # Mínimo de 100ms

    def process_tasks(self) -> None:
        """Processa todas as tarefas na fila.
        
        As tarefas são executadas em paralelo respeitando os limites de concorrência
        definidos na configuração. Tarefas que falharem podem ser agendadas para retentativa.
        """
        if not self.tasks and not self.retry_tasks:
            logger.debug(f"Fila '{self.config.name}' vazia, nada a processar")
            return
            
        logger.info(f"Iniciando processamento da fila '{self.config.name}': "
                   f"{len(self.tasks)} tarefas, {len(self.retry_tasks)} retentativas")
        
        # Criar thread pool para processar as tarefas
        with ThreadPoolExecutor() as executor:
            # Processar primeiras tentativas
            first_futures = []
            for task in self.tasks:
                # Esperar por um slot disponível
                self.first_semaphore.acquire()
                
                # Criar função para executar a tarefa e liberar o semáforo
                def process_with_semaphore(task=task):
                    try:
                        return self._run_task(task)
                    finally:
                        self.first_semaphore.release()
                
                # Submeter tarefa para o pool
                future = executor.submit(process_with_semaphore)
                first_futures.append(future)
            
            # Processar retentativas
            retry_futures = []
            for task in self.retry_tasks:
                # Esperar por um slot disponível
                self.retry_semaphore.acquire()
                
                # Criar função para executar a tarefa e liberar o semáforo
                def process_retry_with_semaphore(task=task):
                    try:
                        return self._run_task(task)
                    finally:
                        self.retry_semaphore.release()
                
                # Submeter tarefa para o pool
                future = executor.submit(process_retry_with_semaphore)
                retry_futures.append(future)
            
            # Aguardar todas as tarefas terminarem
            for future in first_futures + retry_futures:
                future.result()  # Isso forçará qualquer exceção não tratada a ser levantada
        
        # Limpar a fila
        self.tasks.clear()
        self.retry_tasks.clear()
        self.stats.retry_tasks = 0
        self.stats.pending_tasks = 0
        
        logger.info(f"Processamento da fila '{self.config.name}' concluído: "
                   f"{self.stats.completed_tasks} sucesso, {self.stats.failed_tasks} falhas")

class TaskManager:
    """Gerenciador de múltiplas filas de tarefas.
    
    Gerencia uma ou mais filas de tarefas, processando-as em paralelo
    em diferentes threads.
    
    Attributes:
        queues: Lista de filas a serem gerenciadas.
    """
    
    def __init__(self):
        """Inicializa o gerenciador com uma lista vazia de filas."""
        self.queues: List[TaskQueue] = []
        self._processing = False
        logger.debug("TaskManager inicializado")

    def add_queue(self, queue: TaskQueue) -> None:
        """Adiciona uma fila ao gerenciador.
        
        Args:
            queue: Fila a ser adicionada.
        """
        self.queues.append(queue)
        logger.debug(f"Fila '{queue.config.name}' adicionada ao TaskManager")
    
    def is_processing(self) -> bool:
        """Verifica se o processamento das filas está em andamento.
        
        Returns:
            bool: True se o processamento estiver em andamento, False caso contrário.
        """
        return self._processing
    
    def run(self) -> None:
        """Executa o processamento de todas as filas.
        
        Cada fila é processada em sua própria thread, permitindo execução paralela.
        """
        if not self.queues:
            logger.debug("Nenhuma fila a processar")
            return
            
        logger.info(f"Iniciando processamento de {len(self.queues)} filas")
        self._processing = True
        
        try:
            # Criar threads para processar cada fila
            threads = []
            for queue in self.queues:
                thread = threading.Thread(
                    target=queue.process_tasks,
                    name=f"queue-{queue.config.name}"
                )
                thread.daemon = True  # Permitir que o programa termine mesmo que a thread ainda esteja rodando
                threads.append(thread)
                thread.start()
            
            # Aguardar todas as threads terminarem
            for thread in threads:
                thread.join()
                
            logger.info("Processamento de filas concluído")
        finally:
            self._processing = False
