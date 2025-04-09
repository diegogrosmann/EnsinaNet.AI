"""
Tipos relacionados ao padrão Circuit Breaker para resiliência de sistemas.

Define estruturas de dados para implementar o padrão Circuit Breaker,
que previne falhas em cascata em sistemas distribuídos, detectando falhas
e redirecionando chamadas que provavelmente falhariam.
"""
import logging
from typing import Optional, Set, Dict, Any, Callable, TypeVar, Generic, Type, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from .base import T, BaseModel, JSONDict, ResultModel, DataModel, TDataModel, DataModelDict
from .errors import CircuitBreakerError  # Usar o erro centralizado

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para Circuit Breaker
# -----------------------------------------------------------------------------
class CircuitState(Enum):
    """Estados possíveis do Circuit Breaker.
    
    O Circuit Breaker é um padrão de design utilizado para detectar falhas e 
    encapsular a lógica de prevenção de falhas em cascata em sistemas distribuídos.
    
    Valores:
        CLOSED: Estado normal de operação, requisições processadas normalmente.
        OPEN: Estado de falha, requisições são rejeitadas imediatamente.
        HALF_OPEN: Estado de teste limitado para verificar recuperação do sistema.
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"
    
    def __str__(self) -> str:
        """Representação em string do estado.
        
        Returns:
            str: Nome do estado em formato legível.
        """
        return self.value.upper()

@dataclass
class CircuitBreakerConfig(BaseModel):
    """Configuração do Circuit Breaker.
    
    Define os parâmetros que controlam o comportamento do Circuit Breaker,
    como limiares de falha, timeouts e exceções a serem ignoradas.
    
    Args:
        failure_threshold: Número de falhas consecutivas para abrir o circuito.
        reset_timeout: Tempo em segundos que o circuito fica aberto antes de mudar para half-open.
        half_open_timeout: Tempo máximo em segundos que o circuito pode ficar em half-open.
        success_threshold: Número de sucessos consecutivos para fechar o circuito.
        excluded_exceptions: Conjunto de tipos de exceção que não contam como falha.
        service_name: Nome do serviço protegido (para identificação em logs).
    """
    failure_threshold: int = 5
    reset_timeout: float = 60.0
    half_open_timeout: float = 30.0
    success_threshold: int = 2
    excluded_exceptions: Set[Exception] = field(default_factory=set)
    service_name: str = "default"
    
    def __post_init__(self):
        """Valida e registra a criação da configuração."""
        if self.failure_threshold < 1:
            logger.warning(f"Circuit Breaker '{self.service_name}': failure_threshold < 1 é inválido, ajustado para 1")
            self.failure_threshold = 1
            
        if self.success_threshold < 1:
            logger.warning(f"Circuit Breaker '{self.service_name}': success_threshold < 1 é inválido, ajustado para 1")
            self.success_threshold = 1
            
        if self.reset_timeout <= 0:
            logger.warning(f"Circuit Breaker '{self.service_name}': reset_timeout <= 0 é inválido, ajustado para 60s")
            self.reset_timeout = 60.0
            
        logger.info(f"Configuração do Circuit Breaker '{self.service_name}' criada: "
                  f"threshold={self.failure_threshold}, "
                  f"reset={self.reset_timeout}s")
    
    def is_excluded_exception(self, exception: Exception) -> bool:
        """Verifica se uma exceção deve ser ignorada pelo circuit breaker.
        
        Args:
            exception: Exceção a ser verificada.
            
        Returns:
            bool: True se a exceção deve ser ignorada, False caso contrário.
        """
        return any(isinstance(exception, exc_type) for exc_type in self.excluded_exceptions)
    
    def to_dict(self) -> JSONDict:
        """Converte a configuração em um dicionário.
        
        Returns:
            JSONDict: Representação da configuração como dicionário.
        """
        return {
            "failure_threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
            "half_open_timeout": self.half_open_timeout,
            "success_threshold": self.success_threshold,
            "service_name": self.service_name,
            # Não podemos serializar diretamente o set de exceções
            "excluded_exceptions_types": [exc.__name__ for exc in self.excluded_exceptions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CircuitBreakerConfig':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário contendo os dados de configuração.
        
        Returns:
            CircuitBreakerConfig: Nova instância criada a partir dos dados.
        """
        # Removemos excluded_exceptions_types para tratar separadamente
        excluded_exception_names = data.pop('excluded_exceptions_types', [])
        # Criamos a instância com os dados restantes
        instance = cls(**data)
        
        # Opcionalmente, poderia carregar as exceções pelo nome, mas isso requer
        # uma lógica mais complexa para localizar as classes de exceção
        return instance

@dataclass
class CircuitBreakerMetrics(BaseModel):
    """Métricas do Circuit Breaker.
    
    Armazena informações sobre o estado atual do circuit breaker,
    incluindo contadores de falha, sucesso e timestamps de eventos.
    
    Args:
        failure_count: Contador de falhas consecutivas.
        success_count: Contador de sucessos consecutivos.
        last_failure_time: Momento da última falha.
        last_success_time: Momento do último sucesso.
        last_state_change: Momento da última mudança de estado.
        state: Estado atual do circuito.
        total_failures: Total acumulado de falhas (não apenas consecutivas).
        total_successes: Total acumulado de sucessos (não apenas consecutivos).
        total_rejected: Total de requisições rejeitadas por causa do circuito aberto.
    """
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED
    total_failures: int = 0
    total_successes: int = 0
    total_rejected: int = 0
    
    def __post_init__(self):
        """Inicializa o timestamp de mudança de estado se necessário."""
        if not self.last_state_change:
            self.last_state_change = datetime.now()
            
    def reset_counters(self):
        """Reinicia os contadores de falhas e sucessos consecutivos."""
        logger.debug("Reiniciando contadores de circuit breaker")
        self.failure_count = 0
        self.success_count = 0
        
    def record_success(self):
        """Registra uma operação bem-sucedida."""
        self.success_count += 1
        self.total_successes += 1
        self.failure_count = 0  # Reset failure streak on success
        self.last_success_time = datetime.now()
        logger.debug(f"Circuit breaker: sucesso registrado (streak: {self.success_count})")
        
    def record_failure(self):
        """Registra uma operação com falha."""
        self.failure_count += 1
        self.total_failures += 1
        self.success_count = 0  # Reset success streak on failure
        self.last_failure_time = datetime.now()
        logger.debug(f"Circuit breaker: falha registrada (streak: {self.failure_count})")
        
    def record_rejection(self):
        """Registra uma requisição rejeitada devido ao circuito aberto."""
        self.total_rejected += 1
        logger.debug(f"Circuit breaker: requisição rejeitada (total: {self.total_rejected})")
        
    def change_state(self, new_state: CircuitState):
        """Muda o estado do circuit breaker.
        
        Args:
            new_state: Novo estado do circuito.
        """
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.last_state_change = datetime.now()
            logger.info(f"Circuit breaker: estado alterado de {old_state} para {new_state}")
            self.reset_counters()
    
    def should_allow_request(self, config: CircuitBreakerConfig) -> bool:
        """Verifica se uma requisição deve ser permitida com base no estado atual.
        
        Args:
            config: Configuração do circuit breaker.
            
        Returns:
            bool: True se a requisição deve ser permitida, False caso contrário.
        """
        now = datetime.now()
        
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            # Verificar se passou tempo suficiente para tentar half-open
            if (now - self.last_state_change).total_seconds() >= config.reset_timeout:
                self.change_state(CircuitState.HALF_OPEN)
                return True
            return False
            
        # Estado HALF_OPEN
        # No estado half-open, apenas um número limitado de requisições é permitido
        # para testar se o serviço voltou ao normal
        return True

    def get_summary(self) -> Dict[str, Any]:
        """Retorna um resumo das métricas atuais.
        
        Returns:
            Dict[str, Any]: Dicionário com resumo das métricas.
        """
        now = datetime.now()
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_rejected": self.total_rejected,
            "time_in_current_state": (now - self.last_state_change).total_seconds() if self.last_state_change else 0,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None
        }
    
    def to_dict(self) -> JSONDict:
        """Converte as métricas em um dicionário.
        
        Returns:
            JSONDict: Representação das métricas como dicionário.
        """
        return {
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None,
            "state": self.state.value,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_rejected": self.total_rejected,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CircuitBreakerMetrics':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário contendo os dados das métricas.
        
        Returns:
            CircuitBreakerMetrics: Nova instância criada a partir dos dados.
        """
        # Clone os dados para não modificar o original
        data_copy = data.copy()
        
        # Converter strings ISO para objetos datetime
        for date_field in ['last_failure_time', 'last_success_time', 'last_state_change']:
            if date_field in data_copy and data_copy[date_field]:
                data_copy[date_field] = datetime.fromisoformat(data_copy[date_field])
        
        # Converter string de estado para enum
        if 'state' in data_copy:
            data_copy['state'] = CircuitState(data_copy['state'])
        
        return cls(**data_copy)

class CircuitBreakerResult(ResultModel[TDataModel, CircuitBreakerError]):
    """Resultado de operações protegidas por Circuit Breaker.
    
    Encapsula o resultado de operações executadas através do Circuit Breaker,
    fornecendo informações sobre o sucesso/falha da operação e dados adicionais
    sobre o estado do circuito quando relevante.
    
    Attributes:
        circuit_metrics: Métricas atuais do circuit breaker após a operação, quando disponíveis.
    """
    circuit_metrics: Optional[Dict[str, Any]] = None
    
    @classmethod
    def error_model_class(cls) -> Type[CircuitBreakerError]:
        """Retorna a classe ErrorModel associada a este CircuitBreakerResult.
        
        Returns:
            Type[CircuitBreakerError]: A classe CircuitBreakerError a ser utilizada.
        """
        return CircuitBreakerError
    
    @classmethod
    def create_success(cls, data: TDataModel, metrics: Optional[CircuitBreakerMetrics] = None) -> 'CircuitBreakerResult[TDataModel]':
        """Cria um resultado de sucesso com dados e métricas opcionais do circuit breaker.
        
        Args:
            data: Dados a serem incluídos no resultado.
            metrics: Métricas atuais do circuit breaker, se disponíveis.
            
        Returns:
            CircuitBreakerResult: Instância com indicação de sucesso.
        """
        result = super().create_success(data)
        if metrics:
            result.circuit_metrics = metrics.get_summary()
        return result
    
    @classmethod
    def create_failure(cls, error: Union[str, CircuitBreakerError], 
                      service_name: str = None, circuit_state: CircuitState = None,
                      metrics: Optional[CircuitBreakerMetrics] = None) -> 'CircuitBreakerResult[TDataModel]':
        """Cria um resultado de falha com informações do circuit breaker.
        
        Args:
            error: Mensagem de erro ou objeto CircuitBreakerError.
            service_name: Nome do serviço associado ao circuit breaker.
            circuit_state: Estado atual do circuit breaker.
            metrics: Métricas atuais do circuit breaker, se disponíveis.
            
        Returns:
            CircuitBreakerResult: Instância com indicação de falha.
        """
        if isinstance(error, str):
            error_obj = CircuitBreakerError.create_from(
                error, service_name=service_name, circuit_state=circuit_state
            )
        else:
            error_obj = error
            
        result = super().create_failure(error_obj)
        if metrics:
            result.circuit_metrics = metrics.get_summary()
        return result
    
    def to_dict(self) -> JSONDict:
        """Converte o resultado em um dicionário.
        
        Returns:
            JSONDict: Representação do resultado como dicionário.
        """
        result = super().to_dict()
        if self.circuit_metrics:
            result['circuit_metrics'] = self.circuit_metrics
        return result

@dataclass
class CircuitBreaker(BaseModel, Generic[T]):
    """Implementação do padrão Circuit Breaker.
    
    Esta classe implementa o padrão Circuit Breaker para proteger
    sistemas contra falhas em cascata, detectando falhas e impedindo
    chamadas que provavelmente falhariam.
    
    Args:
        config: Configuração do circuit breaker.
        metrics: Métricas do circuit breaker.
    """
    config: CircuitBreakerConfig
    metrics: CircuitBreakerMetrics = field(default_factory=CircuitBreakerMetrics)
    
    def __post_init__(self):
        """Inicializa valores padrão se necessário."""
        logger.info(f"Circuit Breaker criado para serviço '{self.config.service_name}'")
    
    def execute(self, func: Callable[..., T], *args, **kwargs) -> CircuitBreakerResult[T]:
        """Executa uma função protegida pelo circuit breaker.
        
        Args:
            func: Função a ser executada.
            *args: Argumentos posicionais para a função.
            **kwargs: Argumentos nomeados para a função.
            
        Returns:
            CircuitBreakerResult: Resultado da operação.
        """
        if not self.metrics.should_allow_request(self.config):
            self.metrics.record_rejection()
            error_msg = f"Circuito aberto para o serviço '{self.config.service_name}'"
            logger.warning(error_msg)
            return CircuitBreakerResult.create_failure(
                error_msg, 
                service_name=self.config.service_name,
                circuit_state=self.metrics.state,
                metrics=self.metrics
            )
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            
            # Se a função retornar um ResultModel, verificamos se é sucesso
            if isinstance(result, ResultModel):
                if not result.success:
                    self.on_failure()
                # Criar um CircuitBreakerResult com base no ResultModel retornado
                if result.success:
                    return CircuitBreakerResult.create_success(result.data, self.metrics)
                else:
                    return CircuitBreakerResult.create_failure(
                        result.error, 
                        service_name=self.config.service_name,
                        circuit_state=self.metrics.state,
                        metrics=self.metrics
                    )
                
            return CircuitBreakerResult.create_success(result, self.metrics)
            
        except Exception as e:
            if not self.config.is_excluded_exception(e):
                self.on_failure()
            logger.error(f"Erro na execução protegida por Circuit Breaker: {str(e)}", exc_info=True)
            return CircuitBreakerResult.create_failure(
                str(e),
                service_name=self.config.service_name,
                circuit_state=self.metrics.state,
                metrics=self.metrics
            )
    
    def on_success(self):
        """Chamado quando uma operação é bem-sucedida."""
        self.metrics.record_success()
        
        # Se estiver em half-open e atingir o threshold de sucessos, fechar o circuito
        if (self.metrics.state == CircuitState.HALF_OPEN and 
                self.metrics.success_count >= self.config.success_threshold):
            self.metrics.change_state(CircuitState.CLOSED)
            logger.info(f"Circuit breaker '{self.config.service_name}' fechado após {self.config.success_threshold} sucessos")
    
    def on_failure(self):
        """Chamado quando uma operação falha."""
        self.metrics.record_failure()
        
        # Se atingir o threshold de falhas, abrir o circuito
        if self.metrics.state == CircuitState.CLOSED and self.metrics.failure_count >= self.config.failure_threshold:
            self.metrics.change_state(CircuitState.OPEN)
            logger.warning(f"Circuit breaker '{self.config.service_name}' aberto após {self.config.failure_threshold} falhas")
        
        # Se estiver em half-open e falhar, voltar para open
        elif self.metrics.state == CircuitState.HALF_OPEN:
            self.metrics.change_state(CircuitState.OPEN)
            logger.warning(f"Circuit breaker '{self.config.service_name}' reaberto após falha em half-open")
    
    def to_dict(self) -> JSONDict:
        """Converte o circuit breaker em um dicionário.
        
        Returns:
            JSONDict: Representação do circuit breaker como dicionário.
        """
        return {
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CircuitBreaker':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário contendo os dados do circuit breaker.
        
        Returns:
            CircuitBreaker: Nova instância criada a partir dos dados.
        """
        config = CircuitBreakerConfig.from_dict(data.get("config", {}))
        metrics = CircuitBreakerMetrics.from_dict(data.get("metrics", {}))
        
        return cls(config=config, metrics=metrics)

