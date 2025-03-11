from typing import TypeVar, Dict, Any, Optional, Union, List, Set, Generic, TypedDict, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

# Tipos básicos
UserID = int
TokenKey = str
JSONDict = Dict[str, Any]

# Tipos adicionais
TrainingJobID = str
ModelName = str
FilePath = str

# Tipos de métricas
class UsageMetrics(TypedDict):
    """Métricas de uso para um token específico"""
    name: str
    total_calls: int
    avg_time: float
    status_codes: Dict[int, int]

# Mapeamento de ID de token para suas métricas
TokenMetrics = Dict[str, UsageMetrics]

# Tipos genéricos
T = TypeVar('T')
ResponseData = TypeVar('ResponseData')

@dataclass
class APIResponse(Generic[T]):
    """Resposta padrão da API"""
    success: bool
    message: str
    data: Optional[T] = None
    error: Optional[str] = None

@dataclass
class TokenData:
    """Dados do token de usuário"""
    key: TokenKey
    name: str
    created_at: datetime
    is_active: bool = True
    permissions: List[str] = None

@dataclass
class AIConfigData:
    """Configuração de IA"""
    id: int
    name: str
    model_name: str
    use_system_message: bool
    configurations: JSONDict
    training_configurations: JSONDict
    enabled: bool = True

@dataclass
class APILogData:
    """Dados de log da API"""
    id: int
    user_token: Optional[str]
    path: str
    method: str
    status_code: int
    execution_time: float
    timestamp: datetime

@dataclass
class TrainingFileData:
    """Dados de arquivo de treinamento"""
    id: int
    user_id: UserID
    name: str
    file_path: FilePath
    uploaded_at: datetime
    file_size: Optional[int] = None
    
    def file_exists(self) -> bool:
        """Verifica se o arquivo existe fisicamente"""
        import os
        return os.path.exists(self.file_path)

@dataclass
class TrainingCaptureData:
    """Dados de captura de treinamento"""
    id: int
    token_id: int
    ai_client_config_id: int
    is_active: bool
    temp_file: Optional[str] = None
    create_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

@dataclass
class TrainingExampleData:
    """Exemplo individual de treinamento"""
    system_message: str
    user_message: str
    response: str

@dataclass
class AITrainingData:
    """Dados de job de treinamento"""
    id: int
    ai_config_id: int
    job_id: TrainingJobID
    status: str
    file_id: Optional[int] = None
    model_name: Optional[ModelName] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0

@dataclass
class CompareRequestData:
    """Estrutura para requisição de comparação"""
    instructor: Dict[str, Any]
    students: Dict[str, Dict[str, Any]]

@dataclass
class AIResponseData:
    """Resposta de uma IA individual"""
    response: str
    model_name: str
    configurations: Dict[str, Any]
    processing_time: float
    error: Optional[str] = None

@dataclass
class CompareResponseData:
    """Resposta completa de comparação"""
    students: Dict[str, Dict[str, AIResponseData]]

@dataclass
class FileDataRequest:
    """Dados de arquivo para processamento"""
    name: str
    content: str  # Base64
    type: str

# Novos tipos do api/constants.py
@dataclass(frozen=True)
class AIClientConfig:
    """Configuração completa para clientes de IA."""
    ai_global_config: Dict[str, Any] = field(default_factory=dict)
    ai_client_config: Dict[str, Any] = field(default_factory=dict)
    prompt_config: Dict[str, str] = field(default_factory=dict)
    kwargs: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ProcessingResult:
    """Resultado de uma operação de processamento."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Novos tipos do api/utils/circuit_breaker.py
class CircuitState(Enum):
    """Estados possíveis do circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

@dataclass
class CircuitConfig:
    """Configuração do circuit breaker."""
    error_threshold: int = 100
    timeout_seconds: int = 30
    success_threshold: int = 1

class CircuitOpenError(Exception):
    """Erro lançado quando o circuito está aberto."""
    pass

# Novos tipos do api/utils/queue_manager.py
@dataclass
class Task:
    """Representa uma tarefa a ser executada."""
    identifier: str
    func: Callable
    args: tuple = ()
    kwargs: Dict = None
    result_callback: Optional[Callable[[str, Any], None]] = None
    attempt: int = 1

@dataclass
class QueueConfig:
    """Configuração de uma fila de tarefas."""
    max_attempts: int
    initial_wait: float
    backoff_factor: float
    randomness_factor: float
    max_parallel_first: int
    max_parallel_retry: int

# Tipos de resposta comuns
ResponseType = Union[Dict[str, Any], List[Any], str, int, float, bool, None]
APIResponseType = APIResponse[ResponseType]

# Constantes
HTTP_METHODS = ('GET', 'POST', 'PUT', 'PATCH', 'DELETE')
STATUS_CHOICES = (
    ('success', 'Success'),
    ('error', 'Error'),
    ('pending', 'Pending'),
)

# Enums personalizados
class ProcessingStatus(Enum):
    """Status de processamento"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AIModelType(Enum):
    """Tipos de modelos de IA"""
    GPT = "gpt"
    GEMINI = "gemini" 
    CLAUDE = "claude"
    LLAMA = "llama"
    CUSTOM = "custom"

class TrainingStatus(Enum):
    """Status de treinamento de modelo"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DocumentType(Enum):
    """Tipos de documento suportados"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    JSON = "json"
    JSONL = "jsonl"

# Funções utilitárias de validação
def validate_compare_request(data: Dict[str, Any]) -> Optional[str]:
    """Valida estrutura de requisição de comparação
    
    Args:
        data: Dados da requisição
        
    Returns:
        Mensagem de erro ou None se válido
    """
    if not isinstance(data, dict):
        return "Dados inválidos: deve ser um objeto"
        
    if 'instructor' not in data:
        return "Dados inválidos: campo 'instructor' é obrigatório"
        
    if 'students' not in data:
        return "Dados inválidos: campo 'students' é obrigatório"
        
    if not isinstance(data['students'], dict) or len(data['students']) == 0:
        return "Dados inválidos: 'students' deve ser um objeto não vazio"
        
    return None
