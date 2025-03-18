"""
Definições de tipos para uso em toda a aplicação.

Este módulo centraliza tipos de dados comuns utilizados em diferentes
partes da aplicação, garantindo consistência nas anotações de tipo,
serialização de dados e validação.
"""

# Importando todos os tipos de seus respectivos módulos
from .base import JSONDict, T
from .ai import AIMessage, AISuccess, AIPromptConfig, AIConfig
from .comparison import (
    AIComparisonData, AISingleComparisonData, AIComparisonResponse,
    AIComparisonResponseCollection
)
from .api_response import APPResponse, APIComparisonResponse
from .training import (
    AITrainingExample, AITrainingExampleCollection, AITrainingCaptureConfig,
    AITrainingFileData, AITrainingStatus, AITrainingResponse
)
from .api import APIFile, APIFileCollection, APIModel, APIModelCollection
from .circuit_breaker import CircuitState, CircuitBreakerConfig, CircuitBreakerMetrics
from .queue import QueueableTask, QueueableTaskCollection, QueueConfig
from .monitoring import HTTP_METHODS, UsageMetrics, TokenMetrics, APILog, DocumentType
from .validation import ValidationResult

# Exportar todos os símbolos
__all__ = [
    # Base
    'JSONDict', 'T',
    
    # AI
    'AIMessage', 'AISuccess', 'AIPromptConfig', 'AIConfig',
    
    # Comparison
    'AIComparisonData', 'AISingleComparisonData', 'AIComparisonResponse',
    'AIComparisonResponseCollection',
    
    # API Response
    'APPResponse', 'APIComparisonResponse',
    
    # Training
    'AITrainingExample', 'AITrainingExampleCollection', 'AITrainingCaptureConfig',
    'AITrainingFileData', 'AITrainingStatus', 'AITrainingResponse',
    
    # API
    'APIFile', 'APIFileCollection', 'APIModel', 'APIModelCollection',
    
    # Circuit Breaker
    'CircuitState', 'CircuitBreakerConfig', 'CircuitBreakerMetrics',
    
    # Queue
    'QueueableTask', 'QueueableTaskCollection', 'QueueConfig',
    
    # Monitoring
    'HTTP_METHODS', 'UsageMetrics', 'TokenMetrics', 'APILog', 'DocumentType',
    
    # Validation
    'ValidationResult',
]
