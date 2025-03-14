"""
Definições de tipos para uso em toda a aplicação.

Este módulo centraliza tipos de dados comuns utilizados em diferentes
partes da aplicação, garantindo consistência nas anotações de tipo,
serialização de dados e validação.
"""
from typing import Callable, List, Optional, Set, TypeVar, Dict, Any, TypedDict, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# -----------------------------------------------------------------------------
# Tipos básicos
# -----------------------------------------------------------------------------

JSONDict = Dict[str, Any]
"""
Representa um dicionário JSON genérico onde as chaves são strings e os valores
podem ser de qualquer tipo. Utilizado para APIs, serialização e deserialização
de dados em formato JSON.
"""

# -----------------------------------------------------------------------------
# Tipos genéricos
# -----------------------------------------------------------------------------

T = TypeVar('T')
"""
Variável de tipo genérica para uso em funções e classes parametrizadas.
Permite a criação de componentes reutilizáveis que preservam informações 
de tipo durante operações genéricas.
"""

# -----------------------------------------------------------------------------
# Tipos para Configurações da IA
# -----------------------------------------------------------------------------
@dataclass
class AIPromptConfig:
    """Configuração de prompt.

    Atributos:
        prompt (str): Texto principal do prompt.
        base_instruction (Optional[str]): Instruções base.
        response (Optional[str]): Resposta padrão associada.
    """
    prompt: str
    base_instruction: str = None
    response: str = None

@dataclass
class AIConfig:
    """Configuração de IA.

    Atributos:
        api_key (str): Chave de acesso à API.
        api_url (str): URL base da API.
        model_name (Optional[str]): Nome do modelo de IA.
        configurations (JSONDict): Configurações gerais.
        use_system_message (bool): Define se usa mensagem de sistema.
        training_configurations (JSONDict): Configurações de treinamento.
        prompt_config (Optional[AIPromptConfig]): Configurações de prompt.
    """
    api_key: str
    api_url: str
    model_name: str = None
    configurations: JSONDict = field(default_factory=dict)
    use_system_message: bool = True
    training_configurations: JSONDict = field(default_factory=dict)
    prompt_config: AIPromptConfig = None

# -----------------------------------------------------------------------------
# Tipos Genericos da IA
# -----------------------------------------------------------------------------
@dataclass
class AIMessage:
    """Mensagem de IA.

    Atributos:
        system_message (str): Mensagem de sistema.
        user_message (str): Mensagem do usuário.
    """
    system_message: str
    user_message: str

@dataclass
class AISuccess:
    success: bool
    error: Optional[str] = None

# -----------------------------------------------------------------------------
# Tipos para Comparacao da IA
# -----------------------------------------------------------------------------
@dataclass
class AIComparisonData:
    """Estrutura para requisição de comparação.

    Atributos:
        instructor (JSONDict): Dados do instrutor.
        students (Dict[str, JSONDict]): Dados dos alunos.
    """
    instructor: JSONDict
    students: Dict[str, JSONDict]

    def __post_init__(self):
        from core.validators import validate_compare_request
        validate_compare_request(self.__dict__)

@dataclass
class AISingleComparisonData:
    """Estrutura para requisição de comparação individual.

    Atributos:
        instructor (JSONDict): Dados do instrutor.
        student (JSONDict): Dados do aluno.
    """
    instructor: JSONDict
    student: JSONDict

@dataclass
class AIComparisonResponse:
    """Resposta de uma IA individual.

    Atributos:
        response (str): Resposta gerada pela IA.
        model_name (str): Nome do modelo utilizado.
        configurations (JSONDict): Configurações específicas.
        processing_time (float): Tempo de processamento.
        error (Optional[str]): Erro ocorrido, se houver.
    """
    model_name: str
    configurations: JSONDict
    processing_time: float
    response: Optional[str] = None
    error: Optional[str] = None


AIComparisonResponseCollection = Dict[str, Dict[str, AIComparisonResponse]]
# Estrutura: {student_id: {ai: AIComparisonResponse}}

# -----------------------------------------------------------------------------
# Tipos para resposta da API
# -----------------------------------------------------------------------------
@dataclass
class APPResponse:
    """Resposta padrão do APP

    Atributos:
        success (bool): Indica sucesso ou falha.
        error (Optional[str]): Descrição do erro caso exista.
        data (Optional[JSONDict]): Dados genéricos da resposta.
    """
    success: bool
    error: Optional[str] = None
    data: Optional[JSONDict] = None

@dataclass
class APIComparisonResponse(APPResponse):
    """Resposta padrão da API.

    Atributos:
        data (Optional[Dict[Literal["students"], Dict[str, Dict[str, AIComparisonResponse]]]]): Dados retornados.
    """
    data: Optional[Dict[Literal["students"], AIComparisonResponseCollection]] = None
    

# -----------------------------------------------------------------------------
# Tipos para Treinamento
# -----------------------------------------------------------------------------
@dataclass
class AITrainingFileData:
    """Dados de arquivo de treinamento.

    Atributos:
        id (int): Identificador do arquivo.
        user_id (int): Identificador do usuário.
        name (str): Nome do arquivo.
        file_path (str): Caminho do arquivo.
        uploaded_at (datetime): Data de upload.
        file_size (Optional[int]): Tamanho do arquivo.
    """
    id: int
    user_id: int
    name: str
    file_path: str
    uploaded_at: datetime
    file_size: Optional[int] = None
    
    def file_exists(self) -> bool:
        """Verifica se o arquivo existe fisicamente"""
        import os
        return os.path.exists(self.file_path)

class AITrainingStatus(Enum):
    """Status de treinamento de modelo"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AITrainingResponse:
    """Dados de job de treinamento.

    Atributos:
        job_id (str): Identificador externo.
        status (str): Status atual.
        model_name (Optional[str]): Nome do modelo treinado.
        error (Optional[str]): Erro ocorrido.
        created_at (datetime): Data de criação.
        updated_at (datetime): Data de última atualização.
        progress (float): Progresso do treinamento.
    """
    job_id: str
    status: AITrainingStatus
    model_name: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0

# -----------------------------------------------------------------------------
# Tipos para API
# -----------------------------------------------------------------------------
@dataclass
class APIFile:
    """Dados de arquivo de treinamento.

    Atributos:
        id (int): Identificador do arquivo.
        filename (str): Nome do arquivo.
    """
    id: str
    filename: str
    bytes: int
    created_at: datetime

APIFileCollection = List[APIFile]

@dataclass
class APIModel:
    id: str
    name: str
    is_fine_tuned: bool

APIModelCollection = List[APIModel]
   
# -----------------------------------------------------------------------------
# Tipos para Captura de Exemplos
# -----------------------------------------------------------------------------
@dataclass
class AITrainingCaptureConfig:
    """Dados de captura de treinamento.

    Atributos:
        id (int): Identificador da configuração.
        token_id (int): Identificador do token.
        ai_client_config_id (int): Configuração de IA associada.
        is_active (bool): Define se está ativo.
        temp_file (Optional[str]): Arquivo temporário.
        create_at (datetime): Data de criação.
        last_activity (datetime): Última atividade.
    """
    id: int
    token_id: int
    ai_client_config_id: int
    is_active: bool
    temp_file: Optional[str] = None
    create_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

@dataclass
class AITrainingExample:
    """Exemplo de treinamento.

    Atributos:
        message (AIMessage): Mensagem enviada.
        response (str): Resposta esperada.
    """
    message: AIMessage
    response: str

@dataclass
class AITrainingExampleCollection:
    """Coleção de exemplos de treinamento com persistência em arquivo.
    
    Esta classe gerencia uma coleção de exemplos de treinamento,
    permitindo carregar de um arquivo, adicionar, remover e salvar exemplos.
    
    Atributos:
        file_path (str): Caminho do arquivo onde os exemplos são armazenados.
        examples (List[AITrainingExample]): Lista de exemplos de treinamento.
        modified (bool): Indica se a coleção foi modificada desde o último salvamento.
    """
    file_path: str
    examples: List[AITrainingExample] = field(default_factory=list)
    modified: bool = False
    
    def __post_init__(self):
        """Inicializa a coleção, carregando do arquivo se ele existir."""
        import os
        if os.path.exists(self.file_path):
            self.load()
        else:
            # Cria o diretório se não existir
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
    
    def add(self, example: AITrainingExample) -> bool:
        """Adiciona um exemplo à coleção.
        
        Args:
            example: O exemplo a ser adicionado.
            
        Returns:
            bool: True se adicionado com sucesso.
        """
        self.examples.append(example)
        self.modified = True
        return True
    
    def remove(self, index: int) -> Optional[AITrainingExample]:
        """Remove um exemplo pelo índice.
        
        Args:
            index: O índice do exemplo a remover.
            
        Returns:
            O exemplo removido ou None se índice inválido.
        """
        if 0 <= index < len(self.examples):
            example = self.examples.pop(index)
            self.modified = True
            return example
        return None
    
    def save(self) -> bool:
        """Salva a coleção no arquivo.
        
        Returns:
            bool: True se salvo com sucesso.
        """
        try:
            import json
            import dataclasses
            
            def serialize_example(obj):
                if isinstance(obj, AITrainingExample):
                    return {
                        "message": {
                            "system_message": obj.message.system_message,
                            "user_message": obj.message.user_message
                        },
                        "response": obj.response
                    }
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.examples, f, default=serialize_example, indent=2)
            self.modified = False
            return True
        except Exception as e:
            print(f"Erro ao salvar exemplos: {e}")
            return False
    
    def load(self) -> bool:
        """Carrega a coleção do arquivo.
        
        Returns:
            bool: True se carregado com sucesso.
        """
        try:
            import json
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.examples = []
            for item in data:
                example = AITrainingExample(
                    message=AIMessage(
                        system_message=item["message"]["system_message"],
                        user_message=item["user_message"]
                    ),
                    response=item["response"]
                )
                self.examples.append(example)
            
            self.modified = False
            return True
        except Exception as e:
            print(f"Erro ao carregar exemplos: {e}")
            return False
            
    def __len__(self) -> int:
        """Retorna a quantidade de exemplos na coleção."""
        return len(self.examples)

# -----------------------------------------------------------------------------
# Tipos para Circuit Breaker
# -----------------------------------------------------------------------------
class CircuitState(Enum):
    """
    Estados possíveis do Circuit Breaker.
    
    O Circuit Breaker é um padrão de design utilizado para detectar falhas e 
    encapsular a lógica de prevenção de falhas em cascata em sistemas distribuídos.
    
    Estados:
        CLOSED: Estado normal de operação, requisições processadas normalmente.
        OPEN: Estado de falha, requisições são rejeitadas imediatamente.
        HALF_OPEN: Estado de teste limitado para verificar recuperação do sistema.
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

@dataclass
class CircuitBreakerConfig:
    """Configuração do Circuit Breaker.

    Atributos:
        failure_threshold (int): Número de falhas para abrir o circuito.
        reset_timeout (float): Tempo aberto antes de half-open.
        half_open_timeout (float): Tempo máximo em half-open.
        success_threshold (int): Sucessos necessários para fechar o circuito.
        excluded_exceptions (Set[Exception]): Exceções ignoradas.
    """
    failure_threshold: int = 5
    reset_timeout: float = 60.0
    half_open_timeout: float = 30.0
    success_threshold: int = 2
    excluded_exceptions: Set[Exception] = field(default_factory=set)

@dataclass
class CircuitBreakerMetrics:
    """Métricas do Circuit Breaker.

    Atributos:
        failure_count (int): Contador de falhas.
        success_count (int): Contador de sucessos.
        last_failure_time (Optional[datetime]): Momento da última falha.
        last_success_time (Optional[datetime]): Momento do último sucesso.
        state (CircuitState): Estado atual do circuito.
    """
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state: CircuitState = CircuitState.CLOSED

# -----------------------------------------------------------------------------
# Tipos para queue e fila de tarefas
# -----------------------------------------------------------------------------
@dataclass
class QueueableTask:
    """Representa uma tarefa a ser executada.

    Atributos:
        identifier (str): Identificador da tarefa.
        func (Callable): Função a ser executada.
        args (tuple): Argumentos posicionais.
        kwargs (Dict): Argumentos nomeados.
        result_callback (Optional[Callable]): Callback de resultado.
        attempt (int): Número de tentativas.
    """
    identifier: str
    func: Callable
    args: tuple = ()
    kwargs: Dict = field(default_factory=dict)
    result_callback: Optional[Callable[[str, Any], None]] = None
    attempt: int = 1

QueueableTaskCollection = List[QueueableTask]

@dataclass
class QueueConfig:
    """Configuração da fila de tarefas.

    Atributos:
        name (str): Nome da fila.
        max_retries (int): Máximo de tentativas.
        retry_delay (float): Intervalo entre tentativas.
        timeout (float): Tempo máximo de execução.
        max_concurrent (int): Máximo de tarefas em paralelo.
        priority (int): Prioridade padrão da fila.
    """
    name: str
    max_attempts: int = 3  # Removida a vírgula incorreta
    initial_wait: float = 30
    backoff_factor: float = 2
    randomness_factor: float = 0.2
    max_parallel_first: int = -1
    max_parallel_retry: int = 1
    timeout: float = 300.0

# -----------------------------------------------------------------------------
# Tipos para Métricas e Monitoramento e Logs
# -----------------------------------------------------------------------------
HTTP_METHODS = [
    ('GET', 'GET'),
    ('POST', 'POST'),
    ('PUT', 'PUT'),
    ('PATCH', 'PATCH'),
    ('DELETE', 'DELETE'),
]
"""Métodos HTTP suportados pela API."""

class UsageMetrics(TypedDict):
    """
    Métricas de uso para um token específico.
    
    Rastreia estatísticas importantes como número total de chamadas,
    tempo médio de resposta e distribuição de códigos de status HTTP.
    Utilizado para análise de uso da API e monitoramento de performance.
    """
    name: str  # Nome descritivo do token para identificação fácil
    total_calls: int  # Número total de chamada2s de API realizadas com este token
    avg_time: float  # Tempo médio de resposta em milissegundos
    status_codes: Dict[int, int]  # Mapeamento de códigos de status HTTP (ex: 200, 404) para quantidade de ocorrências

TokenMetrics = Dict[str, UsageMetrics]
"""
Mapeamento de IDs de tokens para suas respectivas métricas de uso.
Geralmente usado para agregar dados de uso da API por token,
facilitando o rastreamento e geração de relatórios de utilização.
"""

@dataclass
class APILog:
    """Dados de log da API.

    Atributos:
        id (int): Identificador do log.
        user_token (Optional[str]): Token do usuário.
        request_method (str): Método da requisição.
        request_path (str): Caminho solicitado.
        request_body (Optional[str]): Corpo enviado.
        response_body (Optional[str]): Corpo de resposta.
        status_code (int): Código de status HTTP.
        execution_time (float): Tempo de execução.
        requester_ip (str): IP do requisitante.
        timestamp (datetime): Momento da requisição.
    """
    id: int
    user_token: Optional[str]
    request_method: str
    request_path: str 
    request_body: Optional[str]
    response_body: Optional[str]
    status_code: int
    execution_time: float
    requester_ip: str
    timestamp: datetime

class DocumentType(Enum):
    """Tipos de documento suportados"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    JSON = "json"
    JSONL = "jsonl"