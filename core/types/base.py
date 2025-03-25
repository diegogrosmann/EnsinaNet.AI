"""
Tipos básicos e genéricos para uso em toda a aplicação.

Define tipos comuns reutilizáveis que servem como base para
estruturas de dados mais complexas em todo o sistema.
"""
import logging
from typing import Dict, Any, TypeVar, Generic, Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos básicos
# -----------------------------------------------------------------------------

JSONDict = Dict[str, Any]
"""
Representa um dicionário JSON genérico onde as chaves são strings e os valores
podem ser de qualquer tipo. Utilizado para APIs, serialização e deserialização
de dados em formato JSON.
"""

# -----------------------------------------------------------------------------
# Tipos genéricos
# -----------------------------------------------------------------------------

T = TypeVar('T')
"""
Variável de tipo genérica para uso em funções e classes parametrizadas.
Permite a criação de componentes reutilizáveis que preservam informações 
de tipo durante operações genéricas.
"""

class Result(Generic[T]):
    """Representa o resultado de uma operação que pode ter sucesso ou falha.
    
    Esta classe genérica pode conter um valor de sucesso do tipo T
    ou uma mensagem de erro, facilitando o tratamento de erros sem
    depender exclusivamente de exceções.
    
    Args:
        value: O valor de sucesso (opcional).
        error: A mensagem de erro (opcional).
    """
    def __init__(self, value: Optional[T] = None, error: Optional[str] = None):
        self._value = value
        self._error = error
        
    @property
    def is_success(self) -> bool:
        """Indica se a operação foi bem-sucedida.
        
        Returns:
            bool: True se a operação foi bem-sucedida, False caso contrário.
        """
        return self._error is None
    
    @property
    def value(self) -> T:
        """Retorna o valor de sucesso.
        
        Returns:
            T: O valor de sucesso.
            
        Raises:
            ValueError: Se não houver valor de sucesso.
        """
        if not self.is_success:
            logger.error(f"Tentativa de acessar valor em Result com erro: {self._error}")
            raise ValueError(f"Não há valor disponível: {self._error}")
        return self._value
    
    @property
    def error(self) -> str:
        """Retorna a mensagem de erro.
        
        Returns:
            str: A mensagem de erro.
            
        Raises:
            ValueError: Se não houver mensagem de erro.
        """
        if self.is_success:
            logger.error("Tentativa de acessar erro em Result bem-sucedido")
            raise ValueError("Não há erro disponível")
        return self._error
    
    @classmethod
    def success(cls, value: T) -> 'Result[T]':
        """Cria um resultado de sucesso.
        
        Args:
            value: O valor de sucesso.
            
        Returns:
            Result[T]: Um resultado de sucesso contendo o valor.
        """
        return cls(value=value)
    
    @classmethod
    def failure(cls, error: str) -> 'Result[T]':
        """Cria um resultado de falha.
        
        Args:
            error: A mensagem de erro.
            
        Returns:
            Result[T]: Um resultado de falha contendo a mensagem de erro.
        """
        logger.warning(f"Criando Result de falha: {error}")
        return cls(error=error)
    
    def as_dict(self) -> Dict[str, Any]:
        """Converte o resultado para um dicionário.
        
        Returns:
            Dict: Dicionário representando o resultado.
        """
        if self.is_success:
            return {"success": True, "value": self._value}
        else:
            return {"success": False, "error": self._error}