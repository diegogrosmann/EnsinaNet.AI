"""
Tipos relacionados à validação de dados.
"""
from typing import Optional, Any
from dataclasses import dataclass

# -----------------------------------------------------------------------------
# Classes de resultados
# -----------------------------------------------------------------------------
@dataclass
class ValidationResult:
    """Resultado de uma validação."""
    is_valid: bool
    error_message: Optional[str] = None
    data: Optional[Any] = None
