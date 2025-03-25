"""
Tipos relacionados ao padrão Circuit Breaker para resiliência de sistemas.

Define estruturas de dados para implementar o padrão Circuit Breaker,
que previne falhas em cascata em sistemas distribuídos, detectando falhas
e redirecionando chamadas que provavelmente falhariam.
"""
import logging
from typing import Optional, Set, Dict, Any, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from .result import OperationResult
from core.exceptions import CircuitOpenError

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
class CircuitBreakerConfig:
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

@dataclass
class CircuitBreakerMetrics:
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

T = TypeVar('T')

@dataclass
class CircuitBreaker(Generic[T]):
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
    
    def execute(self, func: Callable[..., T], *args, **kwargs) -> OperationResult[T]:
        """Executa uma função protegida pelo circuit breaker.
        
        Args:
            func: Função a ser executada.
            *args: Argumentos posicionais para a função.
            **kwargs: Argumentos nomeados para a função.
            
        Returns:
            OperationResult: Resultado da operação.
            
        Raises:
            CircuitOpenError: Se o circuito estiver aberto.
        """
        if not self.metrics.should_allow_request(self.config):
            self.metrics.record_rejection()
            error_msg = f"Circuito aberto para o serviço '{self.config.service_name}'"
            logger.warning(error_msg)
            return OperationResult.failed(error_msg)
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            
            # Se a função retornar um OperationResult, verificamos se é sucesso
            if isinstance(result, OperationResult):
                if not result.success:
                    self.on_failure()
                return result
                
            return OperationResult.succeeded(result)
            
        except Exception as e:
            if not self.config.is_excluded_exception(e):
                self.on_failure()
            logger.error(f"Erro na execução protegida por Circuit Breaker: {str(e)}", exc_info=True)
            return OperationResult.failed(str(e))
    
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
