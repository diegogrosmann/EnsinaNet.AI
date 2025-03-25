"""
Módulo de tipos relacionados à validação de dados.

Define estruturas de dados usadas pelos validadores para retornar
resultados de validação de forma padronizada e tipada.
"""
import logging
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Classes de resultados
# -----------------------------------------------------------------------------
@dataclass
class ValidationResult:
    """Resultado de uma validação.
    
    Esta classe encapsula o resultado de uma operação de validação,
    fornecendo informações sobre o status da validação, possíveis
    mensagens de erro e os dados processados/validados.
    
    Args:
        is_valid: Indica se os dados estão válidos.
        error_message: Mensagem de erro caso a validação falhe.
        data: Dados validados ou processados (opcional).
    """
    is_valid: bool
    error_message: Optional[str] = None
    data: Optional[Any] = None
    
    def __post_init__(self):
        """Executa ações após a inicialização da instância."""
        if self.is_valid:
            logger.debug("Validação bem-sucedida")
            if self.error_message:
                logger.warning("Mensagem de erro presente em validação bem-sucedida")
        else:
            logger.warning(f"Validação falhou: {self.error_message}")
            
    def as_dict(self) -> dict:
        """Converte o resultado da validação para um dicionário.
        
        Returns:
            Dict contendo status de validação e mensagem de erro (se houver).
        """
        result = {"valid": self.is_valid}
        if not self.is_valid and self.error_message:
            result["error"] = self.error_message
        if self.data is not None:
            result["data"] = self.data
        return result