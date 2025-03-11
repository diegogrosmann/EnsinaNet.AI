"""Utilitários para manipulação de tipos e conversão de dados.

Este módulo contém funções auxiliares para converter modelos Django em tipos estruturados
e para validação de dados.
"""

from typing import List, Dict, Any, TypeVar, Type, Optional
from datetime import datetime
from dataclasses import is_dataclass, asdict

# Tipo genérico para dataclasses
T = TypeVar('T')

def model_to_dataclass(model_instance: Any, dataclass_type: Type[T]) -> T:
    """Converte uma instância de modelo Django para um objeto dataclass.
    
    Args:
        model_instance: Instância de modelo Django
        dataclass_type: Tipo de dataclass para converter
        
    Returns:
        Objeto dataclass preenchido com dados do modelo
    
    Raises:
        ValueError: Se o tipo alvo não for um dataclass
    """
    if not is_dataclass(dataclass_type):
        raise ValueError(f"{dataclass_type.__name__} não é um dataclass")
    
    # Obter todos os campos para o dataclass
    fields = {f.name for f in dataclass_type.__dataclass_fields__.values()}
    
    # Construir dicionário com valores do modelo
    data = {}
    for field in fields:
        if hasattr(model_instance, field):
            data[field] = getattr(model_instance, field)
    
    # Criar e retornar a instância do dataclass
    return dataclass_type(**data)

def dataclass_to_dict(dataclass_obj: Any) -> Dict[str, Any]:
    """Converte um objeto dataclass para dicionário com tratamento de tipos complexos.
    
    Args:
        dataclass_obj: Objeto dataclass para converter
        
    Returns:
        Dicionário com dados do dataclass
    """
    if not is_dataclass(dataclass_obj):
        raise ValueError(f"Objeto não é um dataclass")
    
    data = asdict(dataclass_obj)
    
    # Processar tipos complexos
    for key, value in data.items():
        # Converter datetime para string
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    
    return data

def list_models_to_dataclasses(model_instances: List[Any], dataclass_type: Type[T]) -> List[T]:
    """Converte uma lista de instâncias de modelo Django para uma lista de dataclasses.
    
    Args:
        model_instances: Lista de instâncias de modelo Django
        dataclass_type: Tipo de dataclass para converter
        
    Returns:
        Lista de objetos dataclass
    """
    return [model_to_dataclass(instance, dataclass_type) for instance in model_instances]
