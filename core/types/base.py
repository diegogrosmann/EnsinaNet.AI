"""
Tipos básicos e genéricos para uso em toda a aplicação.

Define tipos comuns reutilizáveis que servem como base para
estruturas de dados mais complexas em todo o sistema.
"""
from abc import ABC, ABCMeta, abstractmethod
from enum import Enum, EnumMeta
import logging
from typing import Dict, Any, TypeVar, Generic, Optional, List, Iterator, Mapping, Union, Type
from dataclasses import dataclass, field
import uuid

from core.types.mixins import DeserializationMixin, SerializationMixin
from core.exceptions import CoreTypeException
from myproject.exceptions import AppException

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

class BaseModel(ABC, SerializationMixin, DeserializationMixin):
    """Modelo base abstrato para todas as entidades do sistema.
    
    Classe base que define a interface comum para serialização e
    desserialização de modelos em formatos JSON e dicionário.
    """
    pass

TModel = TypeVar('TModel', bound=BaseModel)
"""
Variável de tipo genérica para modelagem de classes derivadas de BaseModel.

Esta variável de tipo é limitada a subclasses de BaseModel, permitindo
a criação de funções e classes genéricas que operam especificamente em
modelos do sistema. Útil para implementações de repositórios, serviços e
outros componentes que precisam manter informações de tipo específicas
durante operações com diferentes modelos.
"""

class BaseModelDict(BaseModel, Generic[TModel], Mapping[str, TModel], ABC):
    """Dicionário tipo-seguro genérico para modelos.
    
    Encapsula um dicionário onde as chaves são strings e os valores são
    instâncias de BaseModel ou seus derivados.
    Implementa a interface Mapping para comportar-se como um dicionário.
    
    Attributes:
        _items: O dicionário interno contendo os modelos.
    """
    _items: Dict[str, TModel] = None

    def __init__(self, items: Union[Dict[str, TModel], None] = None, **kwargs):
        """Inicializa um novo BaseModelDict com os itens fornecidos.
        
        Args:
            items: Dicionário opcional de itens iniciais ou passado diretamente como kwargs.
        """
        self._items = {} if items is None else items

        if kwargs:
            for key, value in kwargs.items():
                self.put_item(key, value)

    def __getitem__(self, key: str) -> TModel:
        return self._items[key]
    
    def __iter__(self) -> Iterator[str]:
        return iter(self._items)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def put_item(self, key: str, item: Optional[TModel] = None, **attrs) -> Optional[TModel]:
        """Adiciona ou atualiza um item no dicionário.
        
        Se o item com a chave especificada já existir, atualiza seus atributos.
        Se o item não existir, adiciona o novo item com a chave fornecida.
        
        Args:
            key: Chave para identificar o item no dicionário.
            item: O item a ser adicionado/atualizado. Se não fornecido,
                 apenas os atributos especificados em attrs serão atualizados.
            **attrs: Atributos a serem atualizados no item, se aplicável.
            
        Returns:
            O item adicionado ou atualizado, ou None se falhar a atualização
            de um item não existente e nenhum novo item for fornecido.
        """
        exists = key in self._items
        target_item = self._items.get(key)
        
        # Caso 1: Atualização de item existente com novo objeto
        if exists and item is not None:
            self._items[key] = item
            logger.debug(f"Item com chave '{key}' substituído no dicionário")
            
            # Atualiza atributos adicionais, se especificados
            if attrs:
                for attr_name, value in attrs.items():
                    if hasattr(item, attr_name):
                        setattr(item, attr_name, value)
                    else:
                        logger.warning(f"Atributo '{attr_name}' não encontrado em item do tipo {type(item).__name__}")
                        
            target_item = item
                
        # Caso 2: Atualização de item existente com atributos
        elif exists and attrs:
            for attr_name, value in attrs.items():
                if hasattr(target_item, attr_name):
                    setattr(target_item, attr_name, value)
                else:
                    logger.warning(f"Atributo '{attr_name}' não encontrado em item do tipo {type(target_item).__name__}")
                    
            logger.debug(f"Atributos do item com chave '{key}' atualizados")
                
        # Caso 3: Adição de novo item
        elif item is not None:
            self._items[key] = item
            logger.debug(f"Item com chave '{key}' adicionado ao dicionário")
            
            # Atualiza atributos adicionais, se especificados
            if attrs:
                for attr_name, value in attrs.items():
                    if hasattr(item, attr_name):
                        setattr(item, attr_name, value)
                    else:
                        logger.warning(f"Atributo '{attr_name}' não encontrado em item do tipo {type(item).__name__}")
                        
            target_item = item
                
        # Caso 4: Tentativa de atualizar item inexistente sem fornecer novo item
        else:
            logger.warning(f"Tentativa de atualizar item não existente: '{key}' sem fornecer novo item")
            return None
            
        # Chama update_timestamp se disponível
        if hasattr(target_item, 'update_timestamp') and callable(getattr(target_item, 'update_timestamp')):
            target_item.update_timestamp()
            
        return target_item
    
    def remove_item(self, key: str) -> Optional[TModel]:
        """Remove um item do dicionário pela sua chave.
        
        Args:
            key: Chave do item a ser removido.
            
        Returns:
            O item removido ou None se não encontrado.
        """
        if key in self._items:
            item = self._items.pop(key)
            logger.debug(f"Item com chave '{key}' removido do dicionário")
            return item
        
        logger.warning(f"Tentativa de remover item não existente: '{key}'")
        return None
    
    def to_dict(self) -> JSONDict:
        """Converte o dicionário de modelos para um dicionário simples.
        
        Returns:
            Um dicionário onde cada valor foi convertido para sua representação
            de dicionário usando o método to_dict().
        """
        result = {}
        
        result['type'] = self.__class__.__name__

        for key, value in self._items.items():
            if hasattr(value, 'to_dict'):
                result[key] = value.to_dict()
            else:
                result[key] = value
                
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModelDict':
        """Cria uma instância de BaseModelDict a partir de um dicionário.
        
        Esta implementação base assume que os itens do dicionário já
        são instâncias do modelo adequado. Subclasses podem sobrescrever
        este método para realizar conversões específicas.
        
        Args:
            data: Dicionário contendo os dados serializados.
            
        Returns:
            Nova instância de BaseModelDict.
        """
        from core.types import get_model_class
        
        dict_type = data.get('type')
        
        if not dict_type:
            raise CoreTypeException(
                "O dicionário não contém o atributo 'type' necessário para desserialização",
                type_name=cls.__name__
            )
        
        dict_class = get_model_class(dict_type)
        if not dict_class:
            raise CoreTypeException(
                f"Tipo de modelo '{dict_type}' não registrado no sistema",
                type_name=dict_type
            )
        
        # Remove o atributo 'type' antes de passar para a criação da instância
        data_copy = data.copy()
        data_copy.pop('type', None)

        items={}
        
        for key, value in data_copy.items():
            items[key] = dict_class.from_dict(value)
                
        return cls(items=items)

class DataModel(BaseModel, Generic[TModel], ABC):
    """Dados de resposta tipados.
    
    Encapsula os dados retornados pela API com seu tipo
    para facilitar o processamento pelo cliente.
    """
        
TDataModel = TypeVar('TDataModel', bound=DataModel)

class DataModelDict(BaseModelDict[TDataModel], ABC):
    """Dicionário tipo-seguro para modelos de dados.
    
    Encapsula um dicionário onde as chaves são strings e os valores são
    instâncias de DataModel ou outro tipo derivado de BaseModel.
    Estende BaseModelDict especializando para DataModel.
    """

TErrorModel = TypeVar('TErrorModel', bound='ErrorModel')
"""
Variável de tipo genérica para modelagem de classes derivadas de ErrorModel.

Esta variável de tipo é limitada a subclasses de ErrorModel, permitindo
a criação de funções e classes genéricas que operam especificamente em
erros tipados do sistema.
"""


@dataclass
class ResultModel(BaseModel, Generic[TDataModel, TErrorModel], ABC):
    """Modelo de resultado genérico abstrato
    
    Estrutura base para resultados de operações, contendo campos para indicar
    sucesso/falha, mensagens de erro e dados do resultado.
    
    Esta é uma classe abstrata que deve ser implementada por subclasses para
    definir o comportamento específico de diferentes tipos de resultados.
    
    Args:
        success: Indica se a operação foi bem-sucedida. Se não for informado,
            será determinado automaticamente com base na presença de dados.
        error: Detalhes do erro caso exista.
        data: Lista de dados tipados do resultado.
    """
    success: Optional[bool] = None
    error: Optional[TErrorModel] = None
    data: Optional[DataModelDict] = None

    @classmethod
    @abstractmethod
    def error_model_class(cls) -> Type[TErrorModel]:
        """Retorna a classe ErrorModel associada a este ResultModel.
        
        Este método abstrato deve ser implementado pelas subclasses para definir
        qual classe ErrorModel específica será usada por este ResultModel.
        
        Returns:
            Type[TErrorModel]: A classe ErrorModel a ser utilizada.
        """
        pass

    def __post_init__(self):
        """Valida e registra a criação do objeto.
        
        Raises:
            ValueError: Se um resultado com sucesso=False não contiver um erro.
            ValueError: Se um resultado com sucesso=True não contiver dados.
        """
        
        # Determina automaticamente o valor de success se não foi informado
        if self.success is None:
            self.success = self.data is not None
            logger.debug(f"Success determinado automaticamente: {self.success}")
        
        # Valida dados para respostas de erro
        if not self.success and self.error is None:
            raise ValueError("Resultado com sucesso=False deve conter um erro.")
        
        # Valida dados para respostas de sucesso
        if self.success and self.data is None:
            raise ValueError("Resultado com sucesso=True deve conter dados.")
    
    @classmethod
    def create_success(cls, data: Union[TDataModel, List[TDataModel]]) -> 'ResultModel[TDataModel, TErrorModel]':
        """Cria um resultado de sucesso.
        
        Args:
            data: Um item de dados individual ou uma lista de itens a serem incluídos no resultado.
            
        Returns:
            Instância com indicação de sucesso e dados fornecidos.
        """
        # Convert single item to list if needed
        if not isinstance(data, list):
            data = [data]
            
        return cls(data=data)
    
    @classmethod
    def with_data_item(cls, item: TDataModel) -> 'ResultModel[TDataModel, TErrorModel]':
        """Cria um resultado de sucesso com um único item de dados.
        
        Args:
            item: Item de dados único a ser incluído no resultado.
            
        Returns:
            Instância com indicação de sucesso e o item fornecido.
        """
        return cls(data=[item])
    
    @classmethod
    def create_failure(cls, error: Union[str, TErrorModel]) -> 'ResultModel[TDataModel, TErrorModel]':
        """Cria um resultado de falha.
        
        Args:
            error: Mensagem de erro (string) ou objeto de erro.
            
        Returns:
            Instância com indicação de falha e erro fornecido.
            
        Raises:
            CoreTypeError: Se o erro for de um tipo não suportado.
        """
        error_obj = error
        if isinstance(error, str):
            error_obj = cls.error_model_class().create_from(error)
            
        return cls(success=False, error=error_obj)
    
    @classmethod
    def from_exception(cls, exc: Exception) -> 'ResultModel[TDataModel, TErrorModel]':
        """Cria um resultado a partir de uma exceção.
        
        Args:
            exc: Exceção capturada.
            
        Returns:
            Instância com indicação de falha baseada na exceção.
        """
        error = cls.error_model_class().create_from(exc)
        return cls(success=False, error=error)

TResultModel = TypeVar('TResultModel', bound='ResultModel')

@dataclass
class ErrorModel(BaseModel, ABC):
    """Modelo base abstrato para representação de erros no sistema.
    
    Esta classe fornece uma estrutura consistente para representar erros
    em toda a aplicação, incluindo mensagens de erro, códigos e dados adicionais.
    
    Attributes:
        message: Mensagem de erro legível para humanos.
        code: Código de erro opcional para identificação programática.
        error_id: ID único para rastreamento do erro, gerado automaticamente se não fornecido.
        status_code: Código de status HTTP associado ao erro, se aplicável.
        additional_data: Dados adicionais associados ao erro.
    """
    message: str
    code: Optional[str] = None
    error_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    status_code: Optional[int] = None
    additional_data: JSONDict = field(default_factory=dict)
    
    def __post_init__(self):
        """Garantir que additional_data seja sempre um dicionário."""
        if self.additional_data is None:
            self.additional_data = {}
    
    def __str__(self) -> str:
        """Retorna uma representação em string legível do erro.
        
        Returns:
            String formatada contendo a mensagem de erro e informações adicionais relevantes.
        """
        return f"{self.message}"
    
    @classmethod
    def create_from(cls, source: Union[str, Exception]) -> 'ErrorModel':
        """Cria uma instância de ErrorModel a partir de uma string ou exceção.
        
        Args:
            source: String com a mensagem de erro ou exceção a ser convertida.
            
        Returns:
            Nova instância de ErrorModel.
            
        Raises:
            TypeError: Se o source não for uma string ou exceção.
        """
        if isinstance(source, str):
            return cls(message=source)
        elif isinstance(source, Exception):
            if isinstance(source, AppException):
                additional_data = getattr(source, 'additional_data', {})
                
                return cls(
                    message=str(source),
                    code=getattr(source, 'code', None),
                    error_id=getattr(source, 'error_id', None),
                    status_code=getattr(source, 'status_code', 500),
                    additional_data=additional_data
                )
            else:
                return cls(message=f"Erro interno: {str(source)}", status_code=500)
        else:
            raise TypeError(
                "O argumento deve ser uma string ou uma exceção",
                f"Esperado: Union[str, Exception], Recebido: {type(source).__name__}"
            )

class EnumABCMeta(EnumMeta, ABCMeta):
    """Metaclasse que herda de ambas EnumMeta e ABCMeta."""
    pass

class BaseEnum(BaseModel, Enum, metaclass=EnumABCMeta):
    """Classe base para todas as enumerações do sistema."""
    
    def __str__(self) -> str:
        return self.value

    # Implementa métodos de BaseModel
    def to_dict(self) -> Dict[str, Any]:
        """Converte o status para um dicionário.
        
        Returns:
            Dicionário com o valor do status.
        """
        return {
            'type': self.__class__.__name__,
            'value': self.value
        }    
    
    @classmethod
    def from_string(cls, value: str) -> 'BaseEnum':
        """Cria uma instância do status a partir de uma string.
        
        Args:
            value: String representando o valor do status.
            
        Returns:
            Nova instância do BaseEnum correspondente à string.
            
        Raises:
            ValueError: Se a string não corresponder a um status válido.
        """
        try:
            return cls(value)
        except ValueError:
            raise ValueError(f"Status inválido: {value}")
