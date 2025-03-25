"""
Tipos relacionados a interações com IA e configurações de modelos.

Define estruturas de dados para representar mensagens, configurações
e resultados de operações com modelos de IA.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from .base import JSONDict
from .messaging import AIMessage
from .result import OperationResult
from core.exceptions import AIConfigError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos Genéricos da IA
# -----------------------------------------------------------------------------
@dataclass
class AISuccess:
    """Indica sucesso ou falha em operações de IA.
    
    Estrutura simples para retornar o resultado de operações com IA,
    incluindo possível mensagem de erro em caso de falha.
    
    Args:
        success: Indicador de sucesso da operação.
        error: Mensagem de erro, caso exista.
    """
    success: bool
    error: Optional[str] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if not self.success and not self.error:
            logger.warning("AISuccess com success=False criado sem mensagem de erro")
        if self.success and self.error:
            logger.warning(f"AISuccess com success=True contém mensagem de erro: {self.error}")

# -----------------------------------------------------------------------------
# Tipos para Configurações da IA
# -----------------------------------------------------------------------------
@dataclass
class AIPromptConfig(AIMessage):
    """Configuração de prompt.
    
    Estende AIMessage adicionando uma resposta padrão associada,
    útil para definir exemplos completos de interação.
    
    Args:
        response: Resposta padrão associada ao prompt.
    """
    response: Optional[str] = None
    
    def validate(self) -> bool:
        """Valida se a configuração está completa.
        
        Returns:
            bool: True se válida, False caso contrário.
        """
        valid = bool(self.system_message and self.user_message)
        if not valid:
            logger.warning("AIPromptConfig inválido: mensagens incompletas")
        return valid

@dataclass
class AIConfig:
    """Configuração de IA.
    
    Armazena toda a configuração necessária para interagir com um
    serviço de IA, incluindo credenciais e preferências de interação.
    
    Args:
        api_key: Chave de acesso à API.
        api_url: URL base da API.
        model_name: Nome do modelo de IA.
        configurations: Configurações específicas do modelo (temperatura, tokens, etc).
        use_system_message: Define se usa mensagem de sistema.
        training_configurations: Configurações específicas para treinamento.
        prompt_config: Configurações de prompt padrão.
    """
    api_key: str
    api_url: str
    model_name: Optional[str] = None
    configurations: JSONDict = field(default_factory=dict)
    use_system_message: bool = True
    training_configurations: JSONDict = field(default_factory=dict)
    prompt_config: Optional[AIPromptConfig] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if not self.api_key:
            logger.error("Configuração de IA criada sem api_key")
        if not self.api_url:
            logger.error("Configuração de IA criada sem api_url")
        
        logger.info(f"AIConfig criada para modelo: {self.model_name or 'não especificado'}")
    
    def validate(self) -> OperationResult[bool]:
        """Valida se a configuração está completa.
        
        Returns:
            OperationResult: Resultado da operação de validação.
        """
        issues = []
        
        if not self.api_key:
            issues.append("api_key ausente")
        
        if not self.api_url:
            issues.append("api_url ausente")
        
        # Se não há model_name, mas é obrigatório pela configuração
        if not self.model_name and self.configurations.get("requires_model_name", True):
            issues.append("model_name é obrigatório")
        
        if issues:
            error_message = f"Configuração de IA inválida: {', '.join(issues)}"
            logger.error(error_message)
            return OperationResult.failed(error_message)
        
        return OperationResult.succeeded(True)
    
    def to_dict(self) -> JSONDict:
        """Converte a configuração para um dicionário.
        
        Returns:
            JSONDict: Dicionário com todas as configurações.
        """
        result = asdict(self)
        
        # Converter prompt_config manualmente se existir
        if self.prompt_config:
            result["prompt_config"] = self.prompt_config.to_dict()
            
        return result

class AIModelType(Enum):
    """Tipo de modelo de IA.
    
    Classifica modelos de IA por sua arquitetura ou caso de uso,
    permitindo tratamento específico para cada tipo de modelo.
    
    Valores:
        BASE: Modelo base sem treinamento específico.
        FINE_TUNED: Modelo com ajuste fino para tarefa específica.
        EMBEDDINGS: Modelo especializado em geração de embeddings.
        MULTIMODAL: Modelo que trabalha com múltiplas modalidades (texto, imagem, etc).
    """
    BASE = "base"
    FINE_TUNED = "fine_tuned"
    EMBEDDINGS = "embeddings"
    MULTIMODAL = "multimodal"
    
    def __str__(self) -> str:
        """Representação em string do tipo de modelo.
        
        Returns:
            str: Nome do tipo em formato legível.
        """
        return self.value