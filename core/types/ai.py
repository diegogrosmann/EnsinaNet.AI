"""
Tipos relacionados a interações com IA e configurações de modelos.
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from .base import JSONDict

# -----------------------------------------------------------------------------
# Tipos Genéricos da IA
# -----------------------------------------------------------------------------
@dataclass
class AIMessage:
    """Mensagem de IA.
    
    Args:
        system_message: Mensagem de sistema.
        user_message: Mensagem do usuário.
    """
    system_message: str
    user_message: str

@dataclass
class AISuccess:
    """Indica sucesso ou falha em operações de IA.
    
    Args:
        success: Indicador de sucesso da operação.
        error: Mensagem de erro, caso exista.
    """
    success: bool
    error: Optional[str] = None

# -----------------------------------------------------------------------------
# Tipos para Configurações da IA
# -----------------------------------------------------------------------------
@dataclass
class AIPromptConfig(AIMessage):
    """Configuração de prompt.
    
    Args:
        response: Resposta padrão associada.
    """
    response: str = None

@dataclass
class AIConfig:
    """Configuração de IA.
    
    Args:
        api_key: Chave de acesso à API.
        api_url: URL base da API.
        model_name: Nome do modelo de IA.
        configurations: Configurações gerais.
        use_system_message: Define se usa mensagem de sistema.
        training_configurations: Configurações de treinamento.
        prompt_config: Configurações de prompt.
    """
    api_key: str
    api_url: str
    model_name: str = None
    configurations: JSONDict = field(default_factory=dict)
    use_system_message: bool = True
    training_configurations: JSONDict = field(default_factory=dict)
    prompt_config: AIPromptConfig = None
