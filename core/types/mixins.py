import json
import datetime
from typing import Any, Dict

from core.exceptions import CoreTypeException, CoreValueException, AppException

class SerializationMixin:
    """Mixin que fornece métodos de serialização para modelos.
    
    Fornece implementação padrão para conversão de modelos para
    formatos de dicionário e JSON.
    """
    def _serialize(self) -> Dict[str, Any]:
        """Método interno para realizar a serialização."""
        serialized_data = {}
        serialized_data['type'] = self.__class__.__name__
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            # Tratamento específico para objetos datetime
            if isinstance(value, datetime.datetime):
                serialized_data[key] = {
                    "type": "datetime",
                    "value": value.isoformat()
                }
            elif isinstance(value, datetime.date):
                serialized_data[key] = {
                    "type": "date",
                    "value": value.isoformat()
                }
            elif isinstance(value, list):
                serialized_data[key] = [
                    item.to_dict() if hasattr(item, 'to_dict') 
                    else {"type": "datetime", "value": item.isoformat()} if isinstance(item, datetime.datetime)
                    else {"type": "date", "value": item.isoformat()} if isinstance(item, datetime.date)
                    else item
                    for item in value
                ]
            elif hasattr(value, 'to_dict'):
                serialized_data[key] = value.to_dict()
            else:
                serialized_data[key] = value
        return serialized_data
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte o modelo para um dicionário.
        
        Returns:
            Representação do modelo como um dicionário.
        """
        return self._serialize()
    
    def to_json(self) -> str:
        """Converte o modelo para uma string JSON.
        
        Returns:
            Representação do modelo como uma string JSON.
        """
        return json.dumps(self.to_dict())


class DeserializationMixin:
    """Mixin que fornece métodos de desserialização para modelos.
    
    Fornece implementação padrão para criação de modelos a partir
    de formatos de dicionário e JSON.
    """
    
    @staticmethod
    def _process_value(value):
        """Processa valores durante a desserialização, convertendo tipos especiais como datas."""
        if isinstance(value, dict) and "type" in value:
            if value["type"] == "datetime":
                return datetime.datetime.fromisoformat(value["value"])
            elif value["type"] == "date":
                return datetime.date.fromisoformat(value["value"])
            value = DeserializationMixin.from_dict(value)
        return value
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Cria uma instância do modelo a partir de um dicionário.
        
        Args:
            data: Dicionário contendo os dados do modelo.
            
        Returns:
            Nova instância do modelo.
            
        Raises:
            CoreValueException: Se o dicionário contiver valores inválidos.
            AppException: Se ocorrer um erro específico da aplicação.
        """

        from core.types import get_model_class
        try:
            model_type = data.get('type')
            
            if not model_type:
                raise CoreTypeException(
                    "O dicionário não contém o atributo 'type' necessário para desserialização",
                    type_name=cls.__name__
                )
            
            model_class = get_model_class(model_type)
            if not model_class:
                raise CoreTypeException(
                    f"Tipo de modelo '{model_type}' não registrado no sistema",
                    type_name=model_type
                )
            
            # Remove o atributo 'type' antes de passar para a criação da instância
            data_copy = data.copy()
            data_copy.pop('type', None)
            
            # Processa os valores para converter tipos especiais como datas
            processed_data = {}
            for k, v in data_copy.items():
                processed_data[k] = cls._process_value(v)
            
            return model_class(**processed_data)

        except AppException:
            raise
        except Exception as e:
            raise CoreValueException(
                f"Falha ao criar objeto {cls.__name__} a partir de dicionário: {str(e)}", 
                type_name=cls.__name__
            )
    
    @classmethod
    def from_json(cls, json_str: str):
        """Cria uma instância do modelo a partir de uma string JSON.
        
        Args:
            json_str: String JSON contendo os dados do modelo.
            
        Returns:
            Nova instância do modelo.
            
        Raises:
            CoreValueError: Se a string JSON for inválida.
            AppException: Se ocorrer um erro específico da aplicação.
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise CoreValueException(
                f"JSON inválido para {cls.__name__}: {str(e)}", 
                type_name=cls.__name__
            )
        except AppException:
            raise
        except Exception as e:
            raise CoreValueException(
                f"Falha ao criar objeto {cls.__name__} a partir de JSON: {str(e)}", 
                type_name=cls.__name__
            )