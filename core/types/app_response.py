"""
Tipos para respostas padrões da API.

Define estruturas de dados para padronizar as respostas
retornadas pelos endpoints da API, garantindo consistência.
"""
import logging
from typing import Union, Type, Optional, List, Any, Dict
from dataclasses import dataclass

from .base import TDataModel, ResultModel, DataModelDict
from .errors import APPError
from ..exceptions import CoreTypeException

logger = logging.getLogger(__name__)

@dataclass
class APPResponse(ResultModel[TDataModel, APPError]):
    """Resposta padrão da APP
    
    Implementação específica de ResultModel para respostas da API,
    com tratamento adicional para erros de aplicação.
    
    Args:
        success: Indica se a operação foi bem-sucedida.
        error: Detalhes do erro caso exista.
        data: Lista de dados tipados da resposta.
    """
    
    @classmethod
    def error_model_class(cls) -> Type[APPError]:
        """Retorna a classe padrão de error associada a este ResultModel.
        
        Returns:
            Type[APPError]: A classe APPError a ser utilizada.
        """
        return APPError


