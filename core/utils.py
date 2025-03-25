"""Utilitários para manipulação de tipos e conversão de dados.

Este módulo contém funções auxiliares para converter modelos Django em tipos estruturados
e para validação de dados.
"""

import logging
from typing import List, Dict, Any, TypeVar, Type, Optional
from datetime import datetime
from dataclasses import is_dataclass, asdict
from core.exceptions import ApplicationError
from core.types.base import JSONDict

logger = logging.getLogger(__name__)

# Tipo genérico para dataclasses
T = TypeVar('T')

def model_to_dataclass(model_instance: Any, dataclass_type: Type[T]) -> T:
    """Converte uma instância de modelo Django para um objeto dataclass.
    
    Extrai os dados relevantes do modelo Django e cria uma instância
    do dataclass especificado com esses dados.
    
    Args:
        model_instance: Instância do modelo Django a ser convertida.
        dataclass_type: Tipo do dataclass para criar.
        
    Returns:
        Nova instância do tipo dataclass_type.
    
    Raises:
        ApplicationError: Se o tipo alvo não for um dataclass ou ocorrer erro
    """
    logger.debug(f"Convertendo modelo para dataclass {dataclass_type.__name__}")
    
    try:
        if not is_dataclass(dataclass_type):
            raise ValueError(f"O tipo {dataclass_type.__name__} não é um dataclass")
        
        # Extrair os dados do modelo Django como dicionário
        model_data = {}
        for field in model_instance._meta.fields:
            field_name = field.name
            field_value = getattr(model_instance, field_name)
            model_data[field_name] = field_value
        
        # Criar a instância do dataclass com os dados extraídos
        return dataclass_type(**model_data)
        
    except ValueError as e:
        raise ApplicationError(f"Erro na conversão para dataclass: {str(e)}")
    except Exception as e:
        logger.exception(f"Erro ao converter modelo para dataclass: {str(e)}")
        raise ApplicationError(f"Erro na conversão de tipo: {str(e)}")

def dataclass_to_dict(dataclass_obj: Any) -> JSONDict:
    """Converte um objeto dataclass para dicionário com tratamento de tipos complexos.
    
    Transforma um objeto dataclass em um dicionário, tratando tipos especiais
    como datetime para garantir serialização adequada.
    
    Args:
        dataclass_obj: Objeto dataclass a ser convertido.
        
    Returns:
        JSONDict: Dicionário com os atributos do dataclass.
        
    Raises:
        ApplicationError: Se o objeto fornecido não for um dataclass ou ocorrer erro
    """
    logger.debug(f"Convertendo dataclass para dicionário")
    
    try:
        if not is_dataclass(dataclass_obj):
            raise ValueError(f"O objeto não é um dataclass")
        
        # Converter para dicionário usando asdict
        result = asdict(dataclass_obj)
        
        # Processar tipos especiais (datetime, etc.)
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        
        return result
        
    except ValueError as e:
        raise ApplicationError(f"Erro na conversão para dicionário: {str(e)}")
    except Exception as e:
        logger.exception(f"Erro ao converter dataclass para dicionário: {str(e)}")
        raise ApplicationError(f"Erro na conversão para dicionário: {str(e)}")

def list_models_to_dataclasses(model_instances: List[Any], dataclass_type: Type[T]) -> List[T]:
    """Converte uma lista de instâncias de modelo Django para uma lista de dataclasses.
    
    Aplica a conversão model_to_dataclass para cada elemento da lista.
    
    Args:
        model_instances: Lista de instâncias de modelo Django.
        dataclass_type: Tipo do dataclass para criar para cada instância.
        
    Returns:
        List[T]: Lista de instâncias do dataclass especificado.
        
    Raises:
        ApplicationError: Se ocorrer erro durante a conversão
    """
    logger.debug(f"Convertendo lista de {len(model_instances)} modelos para dataclass {dataclass_type.__name__}")
    
    try:
        return [model_to_dataclass(instance, dataclass_type) for instance in model_instances]
    except Exception as e:
        logger.exception(f"Erro ao converter lista de modelos: {str(e)}")
        raise ApplicationError(f"Erro na conversão de lista: {str(e)}")
