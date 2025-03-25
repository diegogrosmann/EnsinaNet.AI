# ai_config/tests/test_queue_manager.py

import time
import threading
from concurrent.futures import ThreadPoolExecutor

from django.test import TestCase
from unittest.mock import patch, MagicMock

from api.utils.queue_manager import TaskQueue, TaskManager
from core.exceptions import ApplicationError
from core.types import QueueConfig

# Criar uma classe dummy que simula uma tarefa de fila
class DummyTask:
    """Tarefa dummy para testes do TaskQueue.

    Attributes:
        identifier (str): Identificador da tarefa.
        attempt (int): Número de tentativas realizadas.
        executed (bool): Indica se a tarefa foi executada.
    """
    def __init__(self, identifier):
        self.identifier = identifier
        self.attempt = 1
        self.executed = False

    def execute(self):
        """Simula execução com atraso e marca como executada."""
        time.sleep(0.1)
        self.executed = True
        return f"Resultado {self.identifier}"

# Função dummy de callback para armazenar resultados
def dummy_callback(identifier, result):
    dummy_callback.results[identifier] = result

dummy_callback.results = {}

class TaskQueueTest(TestCase):
    """Testa a classe TaskQueue."""

    def setUp(self):
        """Cria uma TaskQueue com configuração simples."""
        # Criação de um config dummy com limites ilimitados (-1)
        class DummyQueueConfig:
            name = "DummyQueue"
            max_parallel_first = -1
            max_parallel_retry = -1
            max_attempts = 3
            initial_wait = 0.05
            backoff_factor = 2
            randomness_factor = 0.1
        self.config = DummyQueueConfig()
        self.queue = TaskQueue(config=self.config)

    def test_add_and_run_task(self):
        """Verifica se uma tarefa dummy é executada corretamente."""
        task = DummyTask("Tarefa1")
        self.queue.add_task(task)
        self.queue.process_tasks()
        self.assertTrue(task.executed)
        self.assertEqual(dummy_callback.results, {})

    def test_task_retry_logic(self):
        """Testa se a tarefa é reexecutada até o número máximo de tentativas."""
        class FailingTask(DummyTask):
            def __init__(self):
                super().__init__("FailTask")
                self.result_callback = None  # Adicionando este atributo

            def execute(self):
                raise Exception("Falha proposital")
        task = FailingTask()
        resultado = self.queue._run_task(task)
        # Como a tarefa sempre falha, _run_task deve retornar None após tentativas
        self.assertIsNone(resultado)
        # Corrigindo: o número correto de tentativas é max_attempts, não max_attempts + 1
        self.assertEqual(task.attempt, 3)

class TaskManagerTest(TestCase):
    """Testa a classe TaskManager."""

    def setUp(self):
        """Cria duas filas com tarefas dummy e as adiciona ao gerenciador."""
        class DummyQueueConfig:
            name = "Queue1"
            max_parallel_first = -1
            max_parallel_retry = -1
            max_attempts = 2
            initial_wait = 0.05
            backoff_factor = 2
            randomness_factor = 0.1
        config1 = DummyQueueConfig()
        self.queue1 = TaskQueue(config=config1)
        self.queue1.add_task(DummyTask("Task1"))
        self.queue1.add_task(DummyTask("Task2"))
        
        class DummyQueueConfig2:
            name = "Queue2"
            max_parallel_first = -1
            max_parallel_retry = -1
            max_attempts = 2
            initial_wait = 0.05
            backoff_factor = 2
            randomness_factor = 0.1
        config2 = DummyQueueConfig2()
        self.queue2 = TaskQueue(config=config2)
        self.queue2.add_task(DummyTask("Task3"))
        
        self.manager = TaskManager()
        self.manager.add_queue(self.queue1)
        self.manager.add_queue(self.queue2)

    def test_run_multiple_queues(self):
        """Testa se o TaskManager processa todas as filas corretamente."""
        self.manager.run()
        # Verifica se todas as tarefas foram executadas
        for queue in [self.queue1, self.queue2]:
            for task in queue.tasks:
                self.assertTrue(task.executed)

# Fim de test_queue_manager.py
