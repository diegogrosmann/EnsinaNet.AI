"""Constantes e tipos de dados para a API.

Define estruturas de dados, enums e configurações utilizadas pela API.
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

@dataclass(frozen=True)
class AIClientConfig:
    """Configuração completa para clientes de IA.

    Attributes:
        ai_global_config: Configurações globais (api_key, api_url).
        ai_client_config: Configurações específicas do cliente.
        prompt_config: Configurações de prompt e respostas.
        kwargs: Parâmetros adicionais flexíveis.
    """
    ai_global_config: Dict[str, Any] = field(default_factory=dict)
    ai_client_config: Dict[str, Any] = field(default_factory=dict)
    prompt_config: Dict[str, str] = field(default_factory=dict)
    kwargs: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ProcessingResult:
    """Resultado de uma operação de processamento.

    Attributes:
        success: Indica sucesso da operação.
        message: Mensagem descritiva do resultado.
        data: Dados retornados (opcional).
        error: Descrição do erro se houver falha.
    """
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TrainingStatus(Enum):
    """Status possíveis de um treinamento de IA.
    
    Attributes:
        NOT_STARTED: Treinamento ainda não iniciado.
        IN_PROGRESS: Treinamento em andamento.
        COMPLETED: Treinamento concluído com sucesso.
        FAILED: Treinamento falhou.
        CANCELLED: Treinamento cancelado.
    """
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

@dataclass(frozen=True)
class TrainingResult:
    """Resultado de uma operação de treinamento.

    Attributes:
        job_id: Identificador único do job.
        status: Status atual do treinamento.
        model_name: Nome do modelo gerado.
        error: Mensagem de erro se falhou.
        created_at: Data/hora de criação.
        completed_at: Data/hora de conclusão.
        details: Informações adicionais.
        progress: Progresso (0.0 a 1.0).
    """
    job_id: str
    status: TrainingStatus
    model_name: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None
    progress: float = 0.0

