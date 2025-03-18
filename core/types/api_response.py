"""
Tipos para respostas padrões da API.
"""
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
from .base import JSONDict
from .comparison import AIComparisonResponseCollection

# -----------------------------------------------------------------------------
# Tipos para resposta da API
# -----------------------------------------------------------------------------
@dataclass
class APPResponse:
    """Resposta padrão do APP
    
    Args:
        success: Indica sucesso ou falha.
        error: Descrição do erro caso exista.
        data: Dados genéricos da resposta.
    """
    success: bool
    error: Optional[str] = None
    data: Optional[JSONDict] = None

    def to_dict(self) -> JSONDict:
        """Converte a instância em um dicionário.
        
        Returns:
            Dicionário contendo os atributos da resposta.
        """
        return {
            'success': self.success,
            'error': self.error,
            'data': self.data
        }

@dataclass
class APIComparisonResponse(APPResponse):
    """Resposta padrão da API.
    
    Args:
        data: Dados retornados estruturados por estudante.
    """
    data: Optional[Dict[Literal["students"], AIComparisonResponseCollection]] = None
