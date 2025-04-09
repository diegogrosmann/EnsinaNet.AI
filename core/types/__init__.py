"""
Definições de tipos para uso em toda a aplicação.

Este módulo centraliza tipos de dados comuns utilizados em diferentes
partes da aplicação, garantindo consistência nas anotações de tipo,
serialização de dados e validação.
"""

import inspect
import importlib
import pkgutil
import sys
from pathlib import Path
from typing import Dict, Type, Optional, List

from .ai_file import (
    AIFile, 
    AIFileDict
)

from .ai import (
    AIResponse, 
    AIPrompt, 
    AIExample, 
    AIConfig, 
    AIExampleDict, 
    AIResponseDict, 
    AIModelType, 
)

from .app_response import (
    APPResponse, 
    APPError
)
    
from .base import (
    BaseModel, 
    JSONDict, 
    DataModel, 
    TDataModel, 
    DataModelDict, 
    T, 
    ResultModel, 
    BaseModelDict,
    ErrorModel
)

from .circuit_breaker import (
    CircuitBreaker, 
    CircuitState, 
    CircuitBreakerResult, 
    CircuitBreakerConfig,  
    CircuitBreakerMetrics,
)

from .comparison import (
    ComparisonTask, 
    ComparisonJob, 
    ComparisonDict,
    SingleComparisonRequestData, 
    ComparisonRequestData,
    AsyncComparisonTask
)

from .errors import ( 
    APPError, 
    TaskError, 
    CircuitBreakerError,
    APIError
)

from .metrics import (
    HTTP_METHODS,
    UsageMetrics,
    TokenMetrics,
    TokenMetricsDict,
    APILog,
    DocumentType
)

from .mixins import (
    SerializationMixin, 
    DeserializationMixin
)

from .operation import (
    OperationData,
    OperationType,
    TDataModel
)

from .queue import (
    QueueProcessor, 
    QueueStats, 
    QueueableTask, 
    QueueConfig
)

from .status import (
    EntityStatus
)

from .task import (
    TaskBase,
    TTaskBase,
    AsyncTask,
    QueueableTask,
    QueueableTaskDict
)
    
from.training import (
    TrainingTask, 
    TrainingJob, 
    TrainingCaptureConfig, 
    TrainingResponse
)

# Registro global de classes para desserialização baseada em tipo
_MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}
_TASK_REGISTRY: Dict[str, Type[BaseModel]] = {}

def get_model_class(class_name: str) -> Optional[Type[BaseModel]]:
    """
    Recupera uma classe registrada pelo nome.
    
    Args:
        class_name: Nome da classe a recuperar
        
    Returns:
        A classe registrada ou None se não encontrada
    """
    return _MODEL_REGISTRY.get(class_name)

def get_task_class(class_name: str) -> Optional[Type[BaseModel]]:
    """
    Recupera uma classe de tarefa registrada pelo nome.
    
    Args:
        class_name: Nome da classe a recuperar
        
    Returns:
        A classe de tarefa registrada ou None se não encontrada
    """
    return _TASK_REGISTRY.get(class_name)

def _get_all_modules(package_name: str) -> List[str]:
    """
    Obtém todos os módulos dentro de um pacote.
    
    Args:
        package_name: Nome do pacote a ser varrido
        
    Returns:
        Lista de nomes de módulos completos
    """
    package = sys.modules[package_name]
    package_path = Path(package.__file__).parent
    modules = []
    
    for _, name, is_pkg in pkgutil.iter_modules([str(package_path)]):
        full_name = f"{package_name}.{name}"
        modules.append(full_name)
        if is_pkg:
            modules.extend(_get_all_modules(full_name))
    
    return modules

def _register_models_from_module(module_name: str) -> None:
    """
    Registra todas as subclasses de BaseModel em um módulo.
    
    Args:
        module_name: Nome completo do módulo
    """
    try:
        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(module):
            # Verifica se o objeto é uma classe e é subclasse de BaseModel
            # mas não registra classes abstratas nem a própria BaseModel
            try:
                if (inspect.isclass(obj) and 
                    obj is not None and 
                    issubclass(obj, BaseModel) and 
                    obj != BaseModel and 
                    not inspect.isabstract(obj)):
                    # Registra diretamente no dicionário em vez de chamar a função
                    _MODEL_REGISTRY[obj.__name__] = obj
                    
                    # Se for uma subclasse de TaskBase, registra também no _TASK_REGISTRY
                    # Importação adiada para evitar ciclo
                    task_module = module_name.split('.')[-1]
                    # Verificar se a classe é uma tarefa sem importação circular
                    is_task = False
                    if task_module == 'task' or hasattr(obj, 'task_id'):
                        is_task = True
                    else:
                        # Verificar na hierarquia de classes
                        for base in obj.__mro__:
                            if base.__name__ == 'TaskBase' or base.__name__ == 'QueueableTask' or base.__name__ == 'AsyncTask':
                                is_task = True
                                break
                    
                    if is_task:
                        _TASK_REGISTRY[obj.__name__] = obj
            except TypeError:
                # Ignora objetos que não são classes válidas para issubclass()
                continue
    except ImportError as e:
        print(f"Não foi possível importar o módulo {module_name}: {e}")

def register_all_models() -> None:
    """
    Registra automaticamente todas as classes de modelo definidas no pacote types.
    
    Esta função percorre todos os módulos no pacote core.types e registra 
    todas as subclasses concretas de BaseModel.
    """
    current_package = __name__
    modules = _get_all_modules(current_package)
    
    # Registra modelos de cada módulo
    for module_name in modules:
        _register_models_from_module(module_name)

# Automaticamente registra todos os modelos quando o pacote é importado
register_all_models()
