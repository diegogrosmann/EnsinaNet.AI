"""
Tipos relacionados a interações com IA e configurações de modelos.

Define estruturas de dados para representar mensagens, configurações
e resultados de operações com modelos de IA.
"""
import logging
import os
import json
from typing import IO, Optional, Dict, Any, Type, Union, List
from io import BytesIO, TextIOBase
from dataclasses import dataclass, field
from enum import Enum

from core.exceptions import CoreValueException

# Importar diretamente de base em vez de . (core.types)
from .base import JSONDict, DataModelDict, DataModel, ResultModel
from .errors import APIError  # Importando APIError

logger = logging.getLogger(__name__)

class AIResult(ResultModel):
    pass


@dataclass
class AIResponse(DataModel):
    """Resposta da IA.
    
    Contém o resultado de uma operação feita por um modelo de IA específico,
    incluindo o texto da resposta e métricas de processamento.
    
    Args:
        model_name: Nome do modelo de IA utilizado.
        configurations: Configurações específicas utilizadas.
        processing_time: Tempo de processamento em segundos.
        response: Resposta gerada pela IA.
        thinking: Texto de pensamento gerado pela IA (opcional).
        error: Erro ocorrido durante o processamento, se houver.
    """
    model_name: str
    configurations: JSONDict
    processing_time: float
    response: Optional[str] = None
    thinking: Optional[str] = None
    error: Optional[APIError] = None

    def __post_init__(self):
        """Valida os dados após inicialização."""
        if not self.response and not self.error:
            raise CoreValueException(
                "Resposta e erro ausentes",
                field="response",
                type_name="AIResponse"
            )

class AIResponseDict(DataModelDict[AIResponse]):
    """Dicionário tipo-seguro para respostas de IA.
    Estrutura:
        "ai_name" = AIResponse
    """

@dataclass
class AIPrompt(DataModel):
    """Prompt para IA.
    
    Representa uma mensagem estruturada para envio a um modelo de IA,
    contendo mensagem do usuário e opcionalmente uma mensagem de sistema.
    
    Args:
        user_message: Mensagem do usuário contendo a requisição.
        system_message: Mensagem de sistema que define o comportamento (opcional).
    """
    user_message: str
    system_message: Optional[str] = None
    
    def to_dict(self) -> JSONDict:
        """Converte o prompt para um dicionário.
        
        Returns:
            Dicionário com as mensagens de sistema e usuário.
        """
        base_dict = super().to_dict()
        base_dict.update({
            "system_message": self.system_message,
            "user_message": self.user_message
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIPrompt':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com dados para criar o objeto.
            
        Returns:
            Nova instância criada a partir dos dados.
        """
        return cls(
            system_message=data.get('system_message', ''),
            user_message=data.get('user_message', '')
        )

@dataclass
class AIExample(AIPrompt):
    """Exemplo de prompt e resposta para IA.
    
    Representa um par de prompt e resposta que pode ser usado para
    treinamento, avaliação ou referência.
    
    Args:
        user_message: Mensagem do usuário contendo a requisição.
        system_message: Mensagem de sistema que define o comportamento (opcional).
        response: Resposta esperada para este exemplo (obrigatório).
    """
    response: Optional[str] = None
    
    def __post_init__(self):
        """Valida os dados após inicialização e lança exceção se inválido."""
        if not self.user_message:
            raise CoreValueException(
                "Mensagem do usuário vazia", 
                field="user_message", 
                type_name="AIExample"
            )
        if self.response is None:
            raise CoreValueException(
                "Resposta ausente", 
                field="response", 
                type_name="AIExample"
            )
        logger.debug(f"AIExample válido criado com mensagem de {len(self.user_message)} caracteres")
    
    def to_dict(self) -> JSONDict:
        """Converte para um dicionário.
        
        Returns:
            Dicionário com os dados do exemplo.
        """
        base_dict = super().to_dict()
        if self.response:
            base_dict["response"] = self.response
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIExample':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com dados para criar o objeto.
            
        Returns:
            Nova instância criada a partir dos dados.
        """
        if 'response' not in data:
            logger.warning("AIExample.from_dict chamado sem campo 'response'")
        
        return cls(
            system_message=data.get('system_message', ''),
            user_message=data.get('user_message', ''),
            response=data.get('response')
        )

class AIExampleDict(DataModelDict[AIExample]):
    """Dicionário tipo-seguro para exemplos de IA.
    Estrutura:
        "example_id" = AIExample
    """
    @classmethod
    def from_file(cls, file_source: Union[str, bytes, os.PathLike, BytesIO, IO, dict]) -> 'AIExampleDict':
        """Carrega exemplos de IA de um arquivo.
        
        Args:
            file_source: Fonte do arquivo. Pode ser um caminho, bytes, 
                         um objeto file-like ou um dicionário.
            
        Returns:
            Dicionário contendo os exemplos de IA carregados.
        """
        examples_dict = cls()
        
        # Processar a fonte do arquivo para obter os dados JSON
        if isinstance(file_source, dict):
            data = file_source
        else:
            if isinstance(file_source, (str, os.PathLike)):
                # É um caminho de arquivo
                with open(file_source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            elif isinstance(file_source, bytes):
                # É uma sequência de bytes
                data = json.loads(file_source.decode('utf-8'))
            else:
                # É um objeto file-like
                data = json.load(file_source)
        
        # Processar os dados como lista de exemplos
        if isinstance(data, list):
            for i, example_data in enumerate(data):
                try:
                    example = AIExample.from_dict(example_data)
                    # Usar um ID baseado no índice como chave
                    examples_dict.put_item(f"{i}", example)
                except Exception as e:
                    logger.warning(f"Erro ao processar exemplo {i}: {str(e)}")
        else:
            # Se é um único exemplo
            try:
                example = AIExample.from_dict(data)
                examples_dict.put_item("0", example)
            except Exception as e:
                logger.warning(f"Erro ao processar exemplo único: {str(e)}")
        
        logger.debug(f"Carregados {len(examples_dict)} exemplos de IA do arquivo")
        return examples_dict
    
    def save_file(self, file_destination: Union[str, os.PathLike, TextIOBase]) -> bool:
        """Salva os exemplos de IA em um arquivo.
        
        Args:
            file_destination: Destino para salvar. Pode ser um caminho de arquivo
                             ou um objeto file-like aberto para escrita.
                
        Returns:
            bool: True se o salvamento foi bem-sucedido, False caso contrário.
        """
        try:
            # Converter os exemplos para uma lista de dicionários e remover o item 'type'
            examples_list = []
            for example in self.values():
                example_dict = example.to_dict()
                if 'type' in example_dict:
                    example_dict.pop('type')
                examples_list.append(example_dict)
            
            # Determinar como salvar com base no tipo de destino
            if isinstance(file_destination, (str, os.PathLike)):
                # É um caminho de arquivo
                with open(file_destination, 'w', encoding='utf-8') as f:
                    json.dump(examples_list, f, ensure_ascii=False, indent=2)
            else:
                # É um objeto file-like
                json.dump(examples_list, file_destination, ensure_ascii=False, indent=2)
            
            logger.debug(f"Salvos {len(self)} exemplos de IA no arquivo")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar exemplos de IA: {str(e)}")
            return False

@dataclass
class AIConfig(DataModel):
    """Configuração de IA.
    
    Armazena toda a configuração necessária para interagir com um
    serviço de IA, incluindo credenciais e preferências de interação.
    
    Args:
        api_key: Chave de acesso à API.
        api_url: URL base da API.
        model_name: Nome do modelo de IA.
        configurations: Configurações específicas do modelo (temperatura, tokens, etc).
        use_system_message: Define se usa mensagem de sistema.
        training_configurations: Configurações específicas para treinamento.
        base_instruction: Instrução base para a IA (system message).
        prompt: Prompt personalizado para a IA.
        responses: Formatos de resposta esperados.
    """
    api_key: str
    api_url: str
    model_name: Optional[str] = None
    configurations: JSONDict = field(default_factory=dict)
    use_system_message: bool = True
    training_configurations: JSONDict = field(default_factory=dict)
    base_instruction: str = ''
    prompt: str = ''
    responses: str = ''
     
    
    def to_dict(self) -> JSONDict:
        """Converte a configuração para um dicionário.
        
        Returns:
            Dicionário com todas as configurações.
        """
        base_dict = super().to_dict()
        base_dict.update({
            "api_key": self.api_key,
            "api_url": self.api_url,
            "model_name": self.model_name,
            "configurations": self.configurations,
            "use_system_message": self.use_system_message,
            "training_configurations": self.training_configurations,
            "base_instruction": self.base_instruction,
            "prompt": self.prompt,
            "responses": self.responses,
        })
            
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIConfig':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com dados para criar o objeto.
            
        Returns:
            Nova instância criada a partir dos dados.
        """
        return cls(
            api_key=data.get('api_key', ''),
            api_url=data.get('api_url', ''),
            model_name=data.get('model_name'),
            configurations=data.get('configurations', {}),
            use_system_message=data.get('use_system_message', True),
            training_configurations=data.get('training_configurations', {}),
            base_instruction=data.get('base_instruction', ''),
            prompt=data.get('prompt', ''),
            responses=data.get('responses', '')
        )

class AIModelType(Enum):
    """Tipo de modelo de IA.
    
    Classifica modelos de IA por sua arquitetura ou caso de uso,
    permitindo tratamento específico para cada tipo de modelo.
    
    Valores:
        BASE: Modelo base sem treinamento específico.
        FINE_TUNED: Modelo com ajuste fino para tarefa específica.
    """
    BASE = "base"
    FINE_TUNED = "fine_tuned"
    
    def __str__(self) -> str:
        """Representação em string do tipo de modelo.
        
        Returns:
            Nome do tipo em formato legível.
        """
        return self.value