"""
Tipos relacionados a tarefas, tanto síncronas quanto assíncronas.

Define estruturas de dados unificadas para representar tarefas executáveis,
incluindo tarefas em background, jobs de processamento, e tarefas na fila.
"""
import logging
import uuid
from typing import Callable, Dict, Optional, Any, TypeVar, Generic, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from .base import JSONDict, Result

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para tarefas de base
# -----------------------------------------------------------------------------
@dataclass
class TaskBase:
    """Base comum para todos os tipos de tarefas.
    
    Define a estrutura básica compartilhada por tarefas síncronas e assíncronas,
    incluindo identificação, timestamps e informações de status.
    
    Args:
        task_id: Identificador único da tarefa.
        created_at: Momento de criação da tarefa.
        updated_at: Momento da última atualização da tarefa.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        logger.debug(f"Tarefa {self.task_id} criada")
    
    def update_timestamp(self):
        """Atualiza o timestamp de última modificação."""
        self.updated_at = datetime.now()
        logger.debug(f"Timestamp da tarefa {self.task_id} atualizado")

# -----------------------------------------------------------------------------
# Tipos para tarefas síncronas (filas)
# -----------------------------------------------------------------------------
@dataclass
class QueueableTask(TaskBase):
    """Representa uma tarefa a ser executada em uma fila.
    
    Encapsula uma função a ser executada de forma síncrona em uma fila
    de processamento, juntamente com seus argumentos e callbacks.
    
    Args:
        func: Função a ser executada.
        identifier: Identificador único da tarefa (substituído por task_id).
        args: Argumentos posicionais para a função.
        kwargs: Argumentos nomeados para a função.
        result_callback: Função de callback para processar o resultado.
        attempt: Número atual de tentativas de execução.
    """
    func: Callable = field(default=None)  # Adicionando um valor padrão para func
    args: tuple = ()
    kwargs: Dict = field(default_factory=dict)
    result_callback: Optional[Callable[[str, Any], None]] = None
    attempt: int = 1
    
    def __post_init__(self):
        """Valida e registra a criação da tarefa."""
        super().__post_init__()
        if not self.func:
            logger.error(f"Tarefa {self.task_id} criada sem função executável")
            raise ValueError("Parâmetro 'func' é obrigatório e deve ser uma função ou método chamável")
            
        if not callable(self.func):
            logger.error(f"Tarefa {self.task_id} criada com func não chamável")
            raise ValueError("Parâmetro 'func' deve ser uma função ou método chamável")
            
        if self.result_callback and not callable(self.result_callback):
            logger.error(f"Tarefa {self.task_id} criada com callback não chamável")
            raise ValueError("Parâmetro 'result_callback' deve ser uma função ou método chamável")
            
        logger.debug(f"Tarefa {self.task_id} criada (tentativa #{self.attempt})")
    
    def execute(self) -> Result[Any]:
        """Executa a tarefa e processa o resultado.
        
        Returns:
            Result: Resultado encapsulado da execução da função.
        """
        logger.info(f"Executando tarefa {self.task_id} (tentativa #{self.attempt})")
        try:
            result = self.func(*self.args, **self.kwargs)
            
            if self.result_callback:
                logger.debug(f"Processando resultado da tarefa {self.task_id} com callback")
                self.result_callback(self.task_id, result)
                
            return Result.success(result)
            
        except Exception as e:
            logger.error(f"Erro ao executar tarefa {self.task_id}: {str(e)}", exc_info=True)
            if self.attempt > 1:
                logger.warning(f"Tarefa {self.task_id} falhou após {self.attempt} tentativas")
            return Result.failure(str(e))

QueueableTaskCollection = List[QueueableTask]
"""Coleção de tarefas executáveis em uma fila."""

@dataclass
class QueueConfig:
    """Configuração da fila de tarefas.
    
    Define parâmetros de comportamento para uma fila de processamento,
    incluindo políticas de retry, paralelismo e timeouts.
    
    Args:
        name: Nome identificador da fila.
        max_attempts: Máximo de tentativas para cada tarefa.
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
    
    def __post_init__(self):
        """Valida e registra a criação da configuração."""
        if self.max_attempts < 1:
            logger.warning(f"Fila {self.name} configurada com max_attempts < 1, ajustando para 1")
            self.max_attempts = 1
            
        if self.initial_wait < 0:
            logger.warning(f"Fila {self.name} configurada com initial_wait negativo, ajustando para 0")
            self.initial_wait = 0
            
        if self.timeout <= 0:
            logger.warning(f"Fila {self.name} configurada com timeout <= 0, ajustando para 60s")
            self.timeout = 60.0
            
        logger.info(f"Configuração de fila '{self.name}' criada: "
                  f"max_attempts={self.max_attempts}, "
                  f"timeout={self.timeout}s")
    
    def calculate_wait_time(self, attempt: int) -> float:
        """Calcula o tempo de espera para uma tentativa específica.
        
        Args:
            attempt: Número da tentativa (começa em 1).
            
        Returns:
            Tempo de espera em segundos.
        """
        if attempt <= 1:
            return 0
            
        # Cálculo do tempo de espera com backoff exponencial
        wait_time = self.initial_wait * (self.backoff_factor ** (attempt - 2))
        
        logger.debug(f"Fila '{self.name}': tempo de espera para tentativa #{attempt}: {wait_time:.1f}s")
        return wait_time
    
    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determina se uma tarefa deve ser tentada novamente após falha.
        
        Args:
            attempt: Número da tentativa atual.
            exception: Exceção que causou a falha.
            
        Returns:
            True se a tarefa deve ser tentada novamente, False caso contrário.
        """
        # Não tentar novamente se já atingiu o limite de tentativas
        if attempt >= self.max_attempts:
            logger.info(f"Fila '{self.name}': limite de {self.max_attempts} tentativas atingido")
            return False
        
        # Por padrão, sempre tentar novamente dentro do limite de tentativas
        logger.debug(f"Fila '{self.name}': agendando nova tentativa ({attempt+1}/{self.max_attempts})")
        return True

# -----------------------------------------------------------------------------
# Tipos para tarefas assíncronas
# -----------------------------------------------------------------------------
class TaskStatus(Enum):
    """Status de uma tarefa.
    
    Representa os possíveis estados de uma tarefa, permitindo 
    rastrear seu progresso desde a criação até a conclusão.
    
    Valores:
        PENDING: Tarefa foi criada mas não iniciou o processamento.
        PROCESSING: Tarefa está sendo processada no momento.
        COMPLETED: Tarefa foi concluída com sucesso.
        FAILED: Tarefa falhou durante o processamento.
        EXPIRED: Tarefa expirou sem ser processada ou consultada.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    
    def __str__(self) -> str:
        """Representação em string do status.
        
        Returns:
            str: Nome do status em formato legível.
        """
        return self.value

T = TypeVar('T')

@dataclass
class AsyncTask(Generic[T], TaskBase):
    """Tarefa assíncrona genérica.
    
    Representa uma tarefa que será processada de forma assíncrona,
    contendo identificador único, status, dados de entrada e resultado.
    
    Args:
        status: Status atual da tarefa.
        input_data: Dados de entrada para a tarefa.
        result: Resultado da tarefa (quando concluída).
        error: Mensagem de erro (quando falha).
        user_id: ID do usuário que criou a tarefa.
        user_token_id: ID do token usado para criar a tarefa.
        expiration: Data e hora de expiração da tarefa.
    """
    status: TaskStatus = TaskStatus.PENDING
    input_data: Optional[Any] = None
    result: Optional[T] = None
    error: Optional[str] = None
    user_id: Optional[int] = None
    user_token_id: Optional[int] = None
    expiration: Optional[datetime] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        super().__post_init__()
        logger.debug(f"AsyncTask {self.task_id} criada com status {self.status}")
    
    def update_status(self, new_status: TaskStatus, error_msg: Optional[str] = None) -> None:
        """Atualiza o status da tarefa.
        
        Args:
            new_status: Novo status da tarefa.
            error_msg: Mensagem de erro (se aplicável).
        """
        old_status = self.status
        self.status = new_status
        self.update_timestamp()
        
        if new_status == TaskStatus.FAILED and error_msg:
            self.error = error_msg
            
        logger.info(f"AsyncTask {self.task_id} atualizada: {old_status} -> {new_status}")
    
    def set_result(self, result: T) -> None:
        """Define o resultado da tarefa e marca como concluída.
        
        Args:
            result: Resultado da tarefa.
        """
        self.result = result
        self.update_status(TaskStatus.COMPLETED)
        logger.info(f"AsyncTask {self.task_id} concluída com sucesso")
    
    def set_failure(self, error_msg: str) -> None:
        """Marca a tarefa como falha com uma mensagem de erro.
        
        Args:
            error_msg: Descrição do erro ocorrido.
        """
        self.update_status(TaskStatus.FAILED, error_msg)
        logger.error(f"AsyncTask {self.task_id} falhou: {error_msg}")
    
    def to_dict(self) -> JSONDict:
        """Converte a tarefa para um dicionário serializável.
        
        Returns:
            JSONDict: Dicionário com os dados da tarefa.
        """
        result = {
            "task_id": self.task_id,
            "status": str(self.status),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
        if self.user_id:
            result["user_id"] = self.user_id
            
        if self.expiration:
            result["expiration"] = self.expiration.isoformat()
            
        if self.status == TaskStatus.COMPLETED and self.result is not None:
            result["result"] = self.result
            
        if self.status == TaskStatus.FAILED and self.error:
            result["error"] = self.error
            
        return result

@dataclass
class AsyncComparisonTask(AsyncTask[Dict[str, Any]]):
    """Tarefa assíncrona específica para comparações.
    
    Especializa AsyncTask para o caso específico de comparações,
    com métodos e propriedades específicas para este tipo de operação.
    
    Args:
        compare_data: Dados de entrada para a comparação.
    """
    compare_data: Optional[JSONDict] = None
    
    def __post_init__(self):
        """Inicializa dados específicos para comparações."""
        super().__post_init__()
        if self.compare_data:
            self.input_data = self.compare_data
            
        # Calcula estatísticas da tarefa
        if self.input_data and isinstance(self.input_data, dict):
            students_count = len(self.input_data.get("students", {}))
            logger.info(f"AsyncComparisonTask {self.task_id} criada com {students_count} alunos")
    
    @property
    def student_count(self) -> int:
        """Retorna o número de alunos na comparação.
        
        Returns:
            int: Número de alunos a serem comparados.
        """
        if not self.input_data or not isinstance(self.input_data, dict):
            return 0
        return len(self.input_data.get("students", {}))
    
    @property
    def is_large_task(self) -> bool:
        """Verifica se é uma tarefa grande que deve ser processada com prioridade baixa.
        
        Returns:
            bool: True se for uma tarefa grande.
        """
        return self.student_count > 5
    
    def get_summary(self) -> JSONDict:
        """Retorna um resumo da tarefa de comparação.
        
        Returns:
            JSONDict: Resumo com informações principais da tarefa.
        """
        base_dict = self.to_dict()
        base_dict["student_count"] = self.student_count
        base_dict["is_large_task"] = self.is_large_task
        
        # Remove dados completos de entrada e resultado para economizar espaço
        if "input_data" in base_dict:
            del base_dict["input_data"]
            
        # Em vez do resultado completo, fornecer apenas informações básicas
        if self.status == TaskStatus.COMPLETED and self.result:
            student_ids = list(self.result.get("students", {}).keys())
            ai_models = set()
            for student_data in self.result.get("students", {}).values():
                ai_models.update(student_data.keys())
            
            # Substitua o resultado completo por um resumo
            base_dict["result_summary"] = {
                "student_count": len(student_ids),
                "student_ids": student_ids[:5] + ["..."] if len(student_ids) > 5 else student_ids,
                "ai_model_count": len(ai_models),
                "ai_models": list(ai_models)[:5] + ["..."] if len(ai_models) > 5 else list(ai_models)
            }
            
            if "result" in base_dict:
                del base_dict["result"]
                
        return base_dict