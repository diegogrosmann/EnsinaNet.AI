from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

@dataclass
class AIClientConfig:
    """Configuração essencial para clientes de IA.

    Args:
        ai_global_config (Dict): Configuração global da API (api_key, api_url, etc.).
        ai_client_config (Dict): Configurações específicas do cliente.
        prompt_config (Dict): Configuração de prompts (base_instruction, prompt, responses).
        kwargs (Dict, optional): Parâmetros adicionais para configuração flexível.
    """
    ai_global_config: Dict = field(default_factory=dict)
    ai_client_config: Dict = field(default_factory=dict)
    prompt_config: Dict = field(default_factory=dict)
    kwargs: Dict = field(default_factory=dict)

@dataclass
class ProcessingResult:
    """Resultado do processamento realizado pelas funções da API.

    Args:
        success (bool): Indica se o processamento foi bem sucedido.
        message (str): Mensagem associada ao resultado.
        data (Optional[Dict], optional): Dados retornados.
        error (Optional[str], optional): Descrição do erro, se houver.
    """
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None

class TrainingStatus(Enum):
    """Status possíveis do treinamento."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TrainingResult:
    """Resultado do treinamento.
    
    Args:
        job_id (str): ID do job de treinamento.
        status (TrainingStatus): Status atual do treinamento.
        model_name (Optional[str]): Nome do modelo se concluído.
        error (Optional[str]): Mensagem de erro se falhou.
        created_at (datetime): Data de criação.
        completed_at (Optional[datetime]): Data de conclusão.
        details (Dict[str, Any]): Detalhes adicionais do treinamento.
    """
    job_id: str
    status: TrainingStatus
    model_name: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    details: Dict[str, Any] = None
    progress: Optional[float] = 0.0

