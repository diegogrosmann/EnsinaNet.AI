"""
Serializadores para conversão entre objetos Python e formatos de dados como JSON.

Este módulo fornece ferramentas para serialização e desserialização de modelos
de dados, com suporte especial para instâncias de BaseModel e DataModel.
"""

import json
import logging
from typing import Dict, Type, Any, Optional, TypeVar, Generic, cast

from core.types import (
    BaseModel, 
    DataModel, 
    JSONDict,
    get_model_class
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class BaseModelSerializer(Generic[T]):
    """
    Serializador genérico para qualquer classe derivada de BaseModel.
    
    Permite conversões entre objetos Python, dicionários e JSON.
    """
    
    def __init__(self, model_class: Type[T]):
        """
        Inicializa o serializador com a classe do modelo.
        
        Args:
            model_class: Classe do modelo que este serializador manipula
        """
        self.model_class = model_class
        # A classe já deve ter sido automaticamente registrada
        # pelo mecanismo de registro automático em core.types
    
    def to_dict(self, instance: T) -> JSONDict:
        """
        Converte uma instância do modelo em um dicionário.
        
        Args:
            instance: Instância do modelo a ser serializada
            
        Returns:
            Representação em dicionário do modelo
        """
        return instance.to_dict()
    
    def to_json(self, instance: T) -> str:
        """
        Converte uma instância do modelo para JSON.
        
        Args:
            instance: Instância do modelo a ser serializada
            
        Returns:
            String JSON representando o modelo
        """
        return json.dumps(self.to_dict(instance))
    
    def from_dict(self, data: Dict[str, Any]) -> T:
        """
        Cria uma instância do modelo a partir de um dicionário.
        
        Args:
            data: Dados do modelo em formato de dicionário
            
        Returns:
            Nova instância do modelo
        """
        # Para DataModel, usamos o campo 'type' para determinar a classe correta
        if issubclass(self.model_class, DataModel) and 'type' in data:
            type_name = data.get('type')
            concrete_class = get_model_class(type_name)
            
            if concrete_class and issubclass(concrete_class, self.model_class):
                return cast(T, concrete_class.from_dict(data))
            else:
                logger.warning(f"Classe '{type_name}' não registrada ou inválida. Usando {self.model_class.__name__}")
        
        return cast(T, self.model_class.from_dict(data))
    
    def from_json(self, json_str: str) -> T:
        """
        Cria uma instância do modelo a partir de uma string JSON.
        
        Args:
            json_str: String JSON com os dados do modelo
            
        Returns:
            Nova instância do modelo
            
        Raises:
            ValueError: Se o JSON for inválido
        """
        try:
            data = json.loads(json_str)
            return self.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {e}")
            raise ValueError(f"JSON inválido: {e}")

def serialize_model(instance: BaseModel) -> JSONDict:
    """
    Função auxiliar para serializar qualquer BaseModel para um dicionário.
    
    Args:
        instance: Instância do modelo a ser serializada
        
    Returns:
        Dicionário representando o modelo
    """
    return instance.to_dict()

def deserialize_model(data: Dict[str, Any], model_class: Optional[Type[T]] = None) -> BaseModel:
    """
    Função auxiliar para desserializar um dicionário para um BaseModel.
    
    Args:
        data: Dados do modelo em formato de dicionário
        model_class: Classe do modelo a ser instanciado (opcional, usado quando 'type' não está disponível)
        
    Returns:
        Nova instância do modelo
        
    Raises:
        ValueError: Se não for possível determinar a classe do modelo
    """
    if 'type' in data:
        type_name = data.get('type')
        cls = get_model_class(type_name)
        if cls:
            return cls.from_dict(data)
    
    if model_class:
        return model_class.from_dict(data)
    
    raise ValueError("Não foi possível determinar a classe do modelo para desserialização")
