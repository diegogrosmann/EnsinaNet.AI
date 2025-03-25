"""
Tipos relacionados a resultados de operações e validações.

Define estruturas de dados padronizadas para representar resultados
de operações, incluindo validações e processamento de dados.
"""
import logging
from typing import Optional, Any, TypeVar, Generic, Dict
from dataclasses import dataclass
from enum import Enum
from .base import JSONDict
from .validation import ValidationResult

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos básicos de resultado
# -----------------------------------------------------------------------------

T = TypeVar('T')

@dataclass
class OperationResult(Generic[T]):
    """Representa o resultado de uma operação que pode ter sucesso ou falha.
    
    Versão com nomenclatura mais explícita do tipo Result original,
    mantendo a mesma funcionalidade e características.
    
    Args:
        success: Indica se a operação foi bem-sucedida.
        value: O valor de sucesso (opcional).
        error: A mensagem de erro (opcional).
    """
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        """Valida o estado do resultado."""
        if self.success and self.error:
            logger.warning(f"OperationResult com success=True contém erro: {self.error}")
        if not self.success and not self.error:
            logger.warning("OperationResult com success=False não possui mensagem de erro")
    
    @classmethod
    def succeeded(cls, value: T) -> 'OperationResult[T]':
        """Cria um resultado de sucesso.
        
        Args:
            value: O valor de sucesso.
            
        Returns:
            OperationResult[T]: Um resultado de sucesso contendo o valor.
        """
        return cls(success=True, value=value)
    
    @classmethod
    def failed(cls, error: str) -> 'OperationResult[T]':
        """Cria um resultado de falha.
        
        Args:
            error: A mensagem de erro.
            
        Returns:
            OperationResult[T]: Um resultado de falha contendo a mensagem de erro.
        """
        logger.warning(f"Criando OperationResult de falha: {error}")
        return cls(success=False, error=error)
    
    def as_dict(self) -> Dict:
        """Converte o resultado para um dicionário.
        
        Returns:
            Dict: Dicionário com os atributos do resultado.
        """
        result = {"success": self.success}
        if self.success and self.value is not None:
            result["value"] = self.value
        if not self.success and self.error:
            result["error"] = self.error
        return result
