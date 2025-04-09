"""
Tipos relacionados a tarefas, tanto síncronas quanto assíncronas.

Define estruturas de dados unificadas para representar tarefas executáveis,
incluindo tarefas em background, jobs de processamento, e tarefas na fila.
"""
import logging
import uuid
from typing import Callable, Dict, Optional, Any, Generic, List, Union, Type, TypeVar
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod

from .base import DataModel, JSONDict, BaseModel, TDataModel, DataModelDict, ResultModel, ErrorModel, BaseModelDict, TModel
from .status import EntityStatus
from .errors import TaskError  # Usar o erro centralizado
from core.exceptions import CoreTypeException, CoreValueException

logger = logging.getLogger(__name__)
   
# -----------------------------------------------------------------------------
# Tipos para tarefas de base
# -----------------------------------------------------------------------------
@dataclass
class TaskBase(BaseModel, ABC):
    """Base comum abstrata para todos os tipos de tarefas.
    
    Define a estrutura básica compartilhada por tarefas síncronas e assíncronas,
    incluindo identificação, timestamps e informações de status.
    Esta é uma classe abstrata e não deve ser instanciada diretamente.
    
    Attributes:
        task_id (str): Identificador único da tarefa.
        created_at (datetime): Momento de criação da tarefa.
        updated_at (datetime): Momento da última atualização da tarefa.
        progress (float): Percentual de conclusão da tarefa (0 a 100).
        error (Optional[TaskError]): Detalhes do erro caso a tarefa falhe.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_data: Optional[TDataModel] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: EntityStatus = EntityStatus.PENDING
    progress: float = 0.0
    error: Optional[TaskError] = None
    result: Optional[TModel] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if not isinstance(self.task_id, str):
            raise CoreTypeException("task_id deve ser uma string")
        logger.debug(f"Tarefa {self.task_id} criada")
    
    def update_timestamp(self) -> None:
        """Atualiza o timestamp de última modificação."""
        self.updated_at = datetime.now()
        logger.debug(f"Timestamp da tarefa {self.task_id} atualizado")
    
    def update_progress(self, progress: float) -> None:
        """Atualiza o progresso de execução da tarefa.
        
        Args:
            progress (float): Valor de progresso entre 0.0 e 100.0.
            message (Optional[str]): Mensagem opcional descrevendo o estado atual.
        
        Raises:
            CoreValueException: Se o valor de progresso estiver fora do intervalo 0-100.
        """
        if not 0.0 <= progress <= 100.0:
            raise CoreValueException("Progresso deve estar entre 0.0 e 100.0")
        
        self.update_timestamp()
        logger.debug(f"Tarefa {self.task_id} progresso atualizado: {self.progress:.1f}%")
    
    def update_status(self, new_status: EntityStatus, error_msg: Optional[str] = None) -> None:
        """Atualiza o status da tarefa.
        
        Args:
            new_status (EntityStatus): Novo status da tarefa.
            error_msg (Optional[str]): Mensagem de erro (se aplicável).
        """
        old_status = self.status
        self.status = new_status
        self.update_timestamp()
        
        if new_status == EntityStatus.FAILED and error_msg:
            self.error = TaskError(
                message=error_msg,
                task_id=self.task_id
            )
            
        logger.info(f"AsyncTask {self.task_id} atualizada: {old_status} -> {new_status}")
    
    def set_result(self, result: BaseModel) -> None:
        """Define o resultado da tarefa e marca como concluída.
        
        Args:
            result: Resultado da tarefa, que deve ser ou ser convertido em um DataModel.
        """
        
        self.result = result    
        self.update_status(EntityStatus.COMPLETED)
        logger.info(f"AsyncTask {self.task_id} concluída com sucesso")
    
    def set_failure(self, error_msg: str) -> None:
        """Marca a tarefa como falha com uma mensagem de erro.
        
        Args:
            error_msg (str): Descrição do erro ocorrido.
        """
        self.update_status(EntityStatus.FAILED, error_msg)
        logger.error(f"AsyncTask {self.task_id} falhou: {error_msg}")

    @abstractmethod
    def execute(self) -> Any:
        """Executa a tarefa.
        
        Método abstrato que deve ser implementado por todas as subclasses
        para definir o comportamento de execução específico da tarefa.
        
        Returns:
            Any: Resultado da execução da tarefa.
        """
        pass

# -----------------------------------------------------------------------------
# Tipos para coleções de tarefas
# -----------------------------------------------------------------------------
TTaskBase = TypeVar('TTaskBase', bound=TaskBase)
"""
Variável de tipo genérica para modelagem de classes derivadas de TaskBase.

Esta variável de tipo é limitada a subclasses de TaskBase, permitindo
a criação de funções e classes genéricas que operam especificamente em
diferentes tipos de tarefas do sistema.
"""

class TaskDict(BaseModelDict[TTaskBase]):
    """Dicionário tipo-seguro para tarefas.
    
    Encapsula um dicionário onde as chaves são strings (normalmente task_id)
    e os valores são instâncias de TaskBase ou seus derivados.
    
    Attributes:
        _items: O dicionário interno contendo as tarefas.
    """
    
    def __init__(self, items=None):
        """Inicializa o dicionário de tarefas.
        
        Args:
            items: Dicionário opcional de itens iniciais.
        """
        super().__init__(items=items or {})
    
    def put_item(self, key_or_item: Union[str, TTaskBase] = None, item: Optional[TTaskBase] = None, **attrs) -> Optional[TTaskBase]:
        """Adiciona ou atualiza uma tarefa no dicionário.
        
        Suporta múltiplas formas de chamada:
        - put_item(task): Adiciona a tarefa usando seu task_id como chave
        - put_item(key, task): Adiciona a tarefa com a chave especificada
        - put_item(key, **attrs): Atualiza atributos da tarefa existente
        
        Args:
            key_or_item: Chave string ou o próprio objeto tarefa.
            item: A tarefa a ser adicionada/atualizada.
            **attrs: Atributos a serem atualizados na tarefa.
        """
        # Detectar se o primeiro parâmetro é uma tarefa em vez de uma chave
        if key_or_item is not None and not isinstance(key_or_item, str) and hasattr(key_or_item, 'task_id'):
            # Primeiro parâmetro é uma tarefa
            item = key_or_item
            key = item.task_id
            logger.debug(f"put_item(task) detectado, usando task_id '{key}' como chave")
        else:
            # Uso normal com a chave como primeiro parâmetro
            key = key_or_item
        """Adiciona ou atualiza uma tarefa no dicionário.
        
        Se o item com a chave especificada já existir, atualiza seus atributos.
        Se o item não existir, adiciona o novo item com a chave fornecida ou
        usando o task_id da tarefa se nenhuma chave for fornecida.
        
        Args:
            key: Chave para identificar o item no dicionário. Se não fornecida, 
                 usa o task_id da tarefa.
            item: A tarefa a ser adicionada/atualizada. Se não fornecida,
                 apenas os atributos especificados em attrs serão atualizados.
            **attrs: Atributos a serem atualizados na tarefa.
            
        Returns:
            A tarefa adicionada ou atualizada, ou None se falhar.
            
        Raises:
            CoreTypeException: Se nem key nem item forem fornecidos, ou 
                              se item for fornecido sem task_id.
        """
        # Se não temos nem key nem item, não podemos fazer nada
        if key is None and item is None:
            logger.error("Tentativa de adicionar/atualizar tarefa sem fornecer chave ou item")
            raise CoreTypeException("É necessário fornecer key ou item para adicionar/atualizar uma tarefa")
        
        # Se temos item mas não key, usamos o task_id do item como key
        if key is None and item is not None:
            if not hasattr(item, 'task_id'):
                raise CoreTypeException("A tarefa deve ter um atributo 'task_id' quando key não é fornecida")
                
            key = item.task_id
        
        # Agora chamamos o método da classe pai com a key determinada
        return super().put_item(key, item, **attrs)
    
    def remove_item(self, task_or_key: Union[str, TTaskBase]) -> Optional[TTaskBase]:
        """Remove uma tarefa do dicionário pelo seu ID ou pelo objeto tarefa.
        
        Args:
            task_or_id: ID da tarefa ou objeto da tarefa a ser removida.
            
        Returns:
            A tarefa removida ou None se não encontrada.
            
        Raises:
            CoreTypeException: Se o objeto tarefa não tiver um atributo task_id.
        """
        # Se for um objeto tarefa, extrai o task_id
        if isinstance(task_or_key, str):
            task_id = task_or_key
        else:
            # Se for uma tarefa, verifica se tem task_id
            if not hasattr(task_or_key, 'task_id'):
                logger.error("Tentativa de remover tarefa sem task_id")
                raise CoreTypeException("O objeto tarefa deve ter um atributo 'task_id'")
                
            task_id = task_or_key.task_id
            logger.debug(f"Usando task_id '{task_id}' extraído do objeto tarefa")
            
        # Agora chamamos o método da classe pai com o task_id extraído
        return super().remove_item(task_id)
    
    def get_by_status(self, status: EntityStatus) -> List[TTaskBase]:
        """Retorna todas as tarefas com um determinado status.
        
        Args:
            status: O status para filtrar as tarefas.
            
        Returns:
            Lista de tarefas com o status especificado.
        """
        return [
            task for task in self._items.values() 
            if hasattr(task, 'status') and task.status == status
        ]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskDict':
        """Cria uma instância de TaskDict a partir de um dicionário.
        
        Args:
            data: Dicionário contendo os dados serializados.
            
        Returns:
            Nova instância de TaskDict.
        """
        from core.types import get_task_class
        
        items_data = data.get('items', {})
        items = {}
        
        for key, value in items_data.items():
            task_type = value.get('type')
            if not task_type:
                logger.warning(f"Item sem tipo definido, ignorando: {key}")
                continue
                
            task_class = get_task_class(task_type)
            
            if task_class:
                try:
                    items[key] = task_class.from_dict(value)
                except Exception as e:
                    logger.error(f"Erro ao deserializar tarefa {key}: {e}")
            else:
                logger.warning(f"Tipo de tarefa não registrado: {task_type}")
                
        return cls(items=items)

# -----------------------------------------------------------------------------
# Tipos para tarefas assíncronas
# -----------------------------------------------------------------------------
@dataclass
class AsyncTask(Generic[TDataModel], TaskBase):
    """Tarefa assíncrona genérica.
    
    Representa uma tarefa que será processada de forma assíncrona,
    contendo identificador único, status, dados de entrada e resultado.
    
    Attributes:
        input_data (Optional[Any]): Dados de entrada para a tarefa.
        result (Optional[TDataModel]): Resultado da tarefa (quando concluída) como um DataModel.
        user_id (Optional[int]): ID do usuário que criou a tarefa.
        user_token_id (Optional[int]): ID do token usado para criar a tarefa.
        expiration (Optional[datetime]): Data e hora de expiração da tarefa.
    """
    operation_id: str = None
    user_id: Optional[int] = None
    token_key: Optional[int] = None
    expiration: Optional[datetime] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        super().__post_init__()
            
        logger.debug(f"AsyncTask {self.task_id} criada com status {self.status}")
    
        
    def to_dict(self) -> JSONDict:
        """Converte a tarefa para um dicionário serializável.
        
        Returns:
            JSONDict: Dicionário com os dados da tarefa.
        """
        result = super().to_dict()
        
        # Adicionar campos específicos
        result.update({
            "status": str(self.status),
        })
        
        if self.user_id:
            result["user_id"] = self.user_id
            
        if self.expiration:
            result["expiration"] = self.expiration.isoformat()
            
        if self.status == EntityStatus.COMPLETED and self.result is not None:
            result["result"] = self.result.to_dict() if hasattr(self.result, 'to_dict') else self.result
            
        if self.status == EntityStatus.FAILED and self.error:
            result["error"] = self.error.to_dict() if hasattr(self.error, 'to_dict') else {"message": str(self.error)}
            
        return result
    
    def execute(self) -> Any:
        """Executa a tarefa assíncrona.
        
        A implementação específica depende do tipo de tarefa assíncrona.
        Por padrão, apenas verifica e registra o status da tarefa.
        
        Returns:
            Any: Resultado da execução, ou None se não houver resultado.
        """
        logger.info(f"Executando AsyncTask {self.task_id} com status {self.status}")
        
        if self.status == EntityStatus.COMPLETED and self.result is not None:
            return self.result
        elif self.status == EntityStatus.FAILED:
            logger.warning(f"Tentativa de executar tarefa {self.task_id} que falhou anteriormente: {self.error}")
            return None
        else:
            logger.debug(f"Tarefa {self.task_id} ainda não completou processamento")
            return None

# -----------------------------------------------------------------------------
# Tipos para Coonfiguração de filas
# ----------------------------------------------------------------------------- 
@dataclass
class QueueConfig(BaseModel):
    """Configuração da fila de tarefas.
    
    Define parâmetros de comportamento para uma fila de processamento,
    incluindo políticas de retry, paralelismo e timeouts.
    
    Attributes:
        name (str): Nome identificador da fila.
        max_attempts (int): Máximo de tentativas para cada tarefa.
        initial_wait (float): Intervalo inicial entre tentativas (segundos).
        backoff_factor (float): Fator de aumento de espera entre tentativas.
        randomness_factor (float): Fator de aleatoriedade para evitar colisões.
        max_parallel_first (int): Máximo de tarefas em paralelo para primeira tentativa (-1 = ilimitado).
        max_parallel_retry (int): Máximo de tarefas em paralelo para retentativas.
        timeout (float): Tempo máximo de execução de uma tarefa (segundos).
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
        if not isinstance(self.name, str):
            raise CoreTypeException("name deve ser uma string")
        
        if not isinstance(self.max_attempts, int):
            raise CoreTypeException("max_attempts deve ser um inteiro")
        if self.max_attempts < 1:
            logger.warning(f"Fila {self.name} configurada com max_attempts < 1, ajustando para 1")
            self.max_attempts = 1
            
        if not isinstance(self.initial_wait, (int, float)):
            raise CoreTypeException("initial_wait deve ser um número")
        if self.initial_wait < 0:
            logger.warning(f"Fila {self.name} configurada com initial_wait negativo, ajustando para 0")
            self.initial_wait = 0
            
        if not isinstance(self.backoff_factor, (int, float)):
            raise CoreTypeException("backoff_factor deve ser um número")
        
        if not isinstance(self.randomness_factor, (int, float)):
            raise CoreTypeException("randomness_factor deve ser um número")
        
        if not isinstance(self.max_parallel_first, int):
            raise CoreTypeException("max_parallel_first deve ser um inteiro")
        
        if not isinstance(self.max_parallel_retry, int):
            raise CoreTypeException("max_parallel_retry deve ser um inteiro")
        
        if not isinstance(self.timeout, (int, float)):
            raise CoreTypeException("timeout deve ser um número")
        if self.timeout <= 0:
            logger.warning(f"Fila {self.name} configurada com timeout <= 0, ajustando para 60s")
            self.timeout = 60.0
            
        logger.info(f"Configuração de fila '{self.name}' criada: "
                  f"max_attempts={self.max_attempts}, "
                  f"timeout={self.timeout}s")
    
    def calculate_wait_time(self, attempt: int) -> float:
        """Calcula o tempo de espera para uma tentativa específica.
        
        Args:
            attempt (int): Número da tentativa (começa em 1).
            
        Returns:
            float: Tempo de espera em segundos.
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
            attempt (int): Número da tentativa atual.
            exception (Exception): Exceção que causou a falha.
            
        Returns:
            bool: True se a tarefa deve ser tentada novamente, False caso contrário.
        """
        # Não tentar novamente se já atingiu o limite de tentativas
        if attempt >= self.max_attempts:
            logger.info(f"Fila '{self.name}': limite de {self.max_attempts} tentativas atingido")
            return False
        
        # Por padrão, sempre tentar novamente dentro do limite de tentativas
        logger.debug(f"Fila '{self.name}': agendando nova tentativa ({attempt+1}/{self.max_attempts})")
        return True

# -----------------------------------------------------------------------------
# Tipos para tarefas síncronas (filas)
# -----------------------------------------------------------------------------
@dataclass
class QueueableTask(TaskBase):
    """Representa uma tarefa a ser executada em uma fila.
    
    Encapsula uma função a ser executada de forma síncrona em uma fila
    de processamento, juntamente com seus argumentos e callbacks.
    
    Attributes:
        func (Callable): Função a ser executada.
        args (tuple): Argumentos posicionais para a função.
        kwargs (Dict): Argumentos nomeados para a função.
        result_callback (Optional[Callable[[str, Any], None]]): Função de callback para processar o resultado.
        attempt (int): Número atual de tentativas de execução.
            """
    func: Callable = field(default=None) 
    args: tuple = ()
    kwargs: Dict = field(default_factory=dict)
    result_callback: Optional[Callable[[str, Any], None]] = None
    attempt: int = 1
        
    def __post_init__(self):
        """Valida e registra a criação da tarefa."""
        super().__post_init__()
        if not self.func:
            logger.error(f"Tarefa {self.task_id} criada sem função executável")
            raise CoreValueException("Parâmetro 'func' é obrigatório e deve ser uma função ou método chamável")
            
        if not callable(self.func):
            logger.error(f"Tarefa {self.task_id} criada com func não chamável")
            raise CoreValueException("Parâmetro 'func' deve ser uma função ou método chamável")
            
        if self.result_callback and not callable(self.result_callback):
            logger.error(f"Tarefa {self.task_id} criada com callback não chamável")
            raise CoreValueException("Parâmetro 'result_callback' deve ser uma função ou método chamável")
            
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise CoreValueException("Parâmetro 'attempt' deve ser um inteiro maior ou igual a 1")
            
        logger.debug(f"Tarefa {self.task_id} criada (tentativa #{self.attempt})")
    
    def execute(self) -> 'QueueableTask':
        """Executa a tarefa e processa o resultado.
        
        Returns:
            QueueableTask: O próprio objeto de tarefa com o resultado da execução.
        """
        logger.info(f"Executando tarefa {self.task_id} (tentativa #{self.attempt})")
        try:
            self.result = self.func(*self.args, **self.kwargs)
            self.status = EntityStatus.COMPLETED
            self.progress = 100.0
            self.update_timestamp()
            
            if self.result_callback:
                logger.debug(f"Processando resultado da tarefa {self.task_id} com callback")
                self.result_callback(self.task_id, self.result)
                
            return self
            
        except Exception as e:
            logger.error(f"Erro ao executar tarefa {self.task_id}: {str(e)}", exc_info=True)
            if self.attempt > 1:
                logger.warning(f"Tarefa {self.task_id} falhou após {self.attempt} tentativas")
                
            # Criar objeto TaskError para representar o erro
            task_error = TaskError(
                message=str(e),
                task_id=self.task_id,
                code="execution_error",
                error_id=str(uuid.uuid4())
            )
            self.error = task_error
            self.status = EntityStatus.FAILED
            self.update_timestamp()
            
            return self
    
    def set_result(self, result: Any) -> None:
        """Define o resultado da tarefa e marca como concluída."""
        super().set_result(result)
        # Adicionando: chama o callback se existir
        if self.result_callback:
            try:
                self.result_callback(self.task_id, result)
            except Exception as e:
                logger.error(f"Erro ao chamar callback: {str(e)}", exc_info=True)

# Define tipos específicos de TaskDict para os diferentes tipos de tarefas
QueueableTaskDict = TaskDict[QueueableTask]
"""Dicionário tipo-seguro para tarefas enfileiráveis."""


