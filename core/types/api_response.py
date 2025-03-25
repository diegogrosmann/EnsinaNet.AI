"""
Tipos para respostas padrões da API.

Define estruturas de dados para padronizar as respostas
retornadas pelos endpoints da API, garantindo consistência.
"""
import logging
from typing import List, Optional, Dict, Any, Literal, TypeVar, Generic
from dataclasses import dataclass, field
from .base import JSONDict
from .result import OperationResult
from .comparison import AIComparisonResponseCollection
from core.exceptions import APIError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para resposta da API
# -----------------------------------------------------------------------------
T = TypeVar('T')

@dataclass
class APIResponse(Generic[T]):
    """Resposta padrão da API.
    
    Estrutura base para todas as respostas da aplicação,
    contendo campos para indicar sucesso/falha, mensagens
    de erro e dados da resposta.
    
    Args:
        success: Indica se a operação foi bem-sucedida.
        error: Descrição do erro caso exista.
        data: Dados genéricos da resposta.
    """
    success: bool
    error: Optional[str] = None
    data: Optional[T] = None

    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if self.success:
            if self.error:
                logger.warning(f"Resposta com sucesso=True contém erro: {self.error}")
        else:
            logger.info(f"Resposta indicando falha: {self.error}")
    
    def to_dict(self) -> JSONDict:
        """Converte a instância em um dicionário.
        
        Serializa a resposta em formato adequado para retorno via API.
        
        Returns:
            JSONDict: Dicionário contendo os atributos da resposta.
        """
        logger.debug(f"Convertendo APIResponse para dicionário (success={self.success})")
        result = {
            'success': self.success
        }
        
        if self.error is not None:
            result['error'] = self.error
            
        if self.data is not None:
            result['data'] = self.data
            
        return result
    
    @classmethod
    def success_response(cls, data: Optional[T] = None) -> 'APIResponse[T]':
        """Cria uma resposta de sucesso.
        
        Args:
            data: Dados a serem incluídos na resposta.
            
        Returns:
            APIResponse: Resposta de sucesso com os dados fornecidos.
        """
        logger.debug("Criando resposta de sucesso")
        return cls(success=True, data=data)
    
    @classmethod
    def error_response(cls, error_message: str) -> 'APIResponse[T]':
        """Cria uma resposta de erro.
        
        Args:
            error_message: Mensagem descritiva do erro.
            
        Returns:
            APIResponse: Resposta de erro com a mensagem fornecida.
        """
        logger.debug(f"Criando resposta de erro: {error_message}")
        return cls(success=False, error=error_message)
    
    @classmethod
    def from_exception(cls, exception: Exception) -> 'APIResponse[T]':
        """Cria uma resposta a partir de uma exceção.
        
        Args:
            exception: Exceção que ocorreu.
            
        Returns:
            APIResponse: Resposta de erro baseada na exceção.
        """
        logger.debug(f"Convertendo exceção {type(exception).__name__} para resposta")
        if isinstance(exception, APIError):
            # Usar informações da APIError
            return cls(success=False, error=str(exception))
        else:
            # Para outras exceções, usar mensagem genérica
            logger.error(f"Exceção não tratada: {type(exception).__name__}", exc_info=True)
            return cls(success=False, error=f"Erro interno: {str(exception)}")
    
    @classmethod
    def from_operation_result(cls, result: OperationResult[T]) -> 'APIResponse[T]':
        """Cria uma resposta a partir de um OperationResult.
        
        Args:
            result: Resultado da operação.
            
        Returns:
            APIResponse: Resposta baseada no resultado.
        """
        logger.debug(f"Convertendo OperationResult para APIResponse (success={result.success})")
        if result.success:
            return cls.success_response(data=result.value)
        else:
            return cls.error_response(error_message=result.error)

@dataclass
class APIComparisonAPIResponse(APIResponse[Dict[Literal["students"], AIComparisonResponseCollection]]):
    """Resposta padrão da API de comparação.
    
    Especialização da resposta padrão para endpoints de comparação,
    contendo estrutura de dados específica para comparações entre
    instrutor e estudantes.
    """
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        super().__post_init__()
        if self.success and self.data:
            student_count = len(self.data.get("students", {}))
            logger.debug(f"Resposta de comparação com {student_count} estudantes")
    
    @classmethod
    def create_successful_comparison(
            cls, comparison_data: AIComparisonResponseCollection) -> 'APIComparisonAPIResponse':
        """Cria uma resposta de comparação bem-sucedida.
        
        Args:
            comparison_data: Dados de comparação estruturados.
            
        Returns:
            APIComparisonAPIResponse: Resposta formatada com os dados fornecidos.
        """
        logger.debug(f"Criando resposta de comparação com sucesso")
        return cls(success=True, data={"students": comparison_data})

# Aliases de tipos comuns de resposta para facilitar o uso
APIResponseDict = APIResponse[Dict[str, Any]]
"""Resposta com dados em formato de dicionário."""

APIResponseList = APIResponse[List[Dict[str, Any]]]
"""Resposta com dados em formato de lista de dicionários."""