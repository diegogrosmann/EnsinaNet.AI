"""
Tipos relacionados a mensagens e comunicação entre sistemas.

Define estruturas de dados para representar mensagens trocadas entre
usuários, sistemas e modelos de IA, incluindo formatação padronizada.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from .base import JSONDict

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos de mensagens básicas
# -----------------------------------------------------------------------------

@dataclass
class Message:
    """Mensagem básica.
    
    Representa uma estrutura básica de mensagem com conteúdo
    e metadados opcionais.
    
    Args:
        content: Conteúdo principal da mensagem.
        metadata: Metadados associados à mensagem (opcional).
    """
    content: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if not self.content:
            logger.warning("Message criada com conteúdo vazio")
        logger.debug(f"Message criada ({len(self.content)} caracteres)")
    
    def to_dict(self) -> JSONDict:
        """Converte a mensagem para um dicionário.
        
        Returns:
            JSONDict: Dicionário com o conteúdo e metadados.
        """
        result = {"content": self.content}
        if self.metadata:
            result["metadata"] = self.metadata
        return result

@dataclass
class AIMessage:
    """Mensagem de IA.
    
    Representa uma troca de mensagens básica com um modelo de IA,
    contendo mensagem de sistema (instruções) e mensagem do usuário.
    
    Args:
        system_message: Mensagem de sistema com instruções para a IA.
        user_message: Mensagem do usuário com a consulta ou solicitação.
    """
    system_message: str
    user_message: str
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if not self.user_message:
            logger.warning("AIMessage criada com user_message vazio")
        logger.debug(f"AIMessage criada (system: {len(self.system_message)} chars, "
                    f"user: {len(self.user_message)} chars)")
    
    def to_dict(self) -> JSONDict:
        """Converte a mensagem para um dicionário.
        
        Returns:
            JSONDict: Dicionário com as mensagens de sistema e usuário.
        """
        return {
            "system_message": self.system_message,
            "user_message": self.user_message
        }
