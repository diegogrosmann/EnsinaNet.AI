"""
Definições de tipos para uso em toda a aplicação.

Este módulo centraliza tipos de dados comuns utilizados em diferentes
partes da aplicação, garantindo consistência nas anotações de tipo,
serialização de dados e validação.
"""

# Tipos básicos
from .base import JSONDict, Result

# Tipos de validação
from .validation import ValidationResult

# Tipos de resultado
from .result import OperationResult

# Tipos de mensagens
from .messaging import Message, AIMessage

# Tipos para tarefas
from .task import TaskBase, TaskStatus, QueueableTask, AsyncTask, AsyncComparisonTask

# Tipos para filas
from .queue import QueueConfig, QueueStats, QueueProcessor

# Tipos para IA
from .ai import AIConfig, AIPromptConfig, AIModelType, AISuccess

# Tipos para comparação
from .comparison import (
    AIComparisonData,
    AISingleComparisonData,
    AIComparisonResponse,
    AIComparisonResponseCollection
)

# Tipos para treinamento
from .training import (
    AITrainingExample,
    AITrainingExampleCollection,
    AITrainingCaptureConfig,
    AITrainingFileData,
    TrainingStatus,
    AITrainingResponse
)

# Tipos para APIs
from .api import APIFile, APIModel
from .api_response import APIResponse, APIComparisonAPIResponse

# Tipos para métricas e monitoramento
from .metrics import TokenMetrics, UsageMetrics, APILog, DocumentType

# Tipos para resiliência
from .circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig