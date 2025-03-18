"""
Tipos relacionados ao treinamento e captura de exemplos para IA.
"""
import io
import json
import os
from typing import List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from .ai import AIMessage
from .base import JSONDict
from core.validators import validate_training_data
from core.exceptions import FileProcessingError

# -----------------------------------------------------------------------------
# Tipos para Captura de Exemplos
# -----------------------------------------------------------------------------
@dataclass
class AITrainingExample(AIMessage):
    """Exemplo de treinamento.
    
    Args:
        response: Resposta esperada.
    """
    response: str
    
    def to_dict(self) -> JSONDict:
        """Converte o exemplo de treinamento para um dicionário serializável em JSON.
        
        Returns:
            Dicionário com os atributos do exemplo de treinamento.
        """
        return {
            "system_message": self.system_message,
            "user_message": self.user_message,
            "response": self.response
        }

@dataclass
class AITrainingExampleCollection:
    """Coleção de exemplos de treinamento com persistência em arquivo.
    
    Esta classe gerencia uma coleção de exemplos de treinamento,
    permitindo carregar de um arquivo, adicionar, remover e salvar exemplos.
    
    Args:
        file_path: Caminho do arquivo onde os exemplos são armazenados.
        examples: Lista de exemplos de treinamento.
        modified: Indica se a coleção foi modificada desde o último salvamento.
    """
    examples: List[AITrainingExample] = field(default_factory=list)       
    
    def to_dict(self) -> List[JSONDict]:
        """Converte a coleção de exemplos de treinamento em formato de dicionário.
        
        Returns:
            Lista de dicionários representando os exemplos de treinamento.
        """
        return [example.to_dict() for example in self.examples]
    
    @staticmethod
    def _process_data(data) -> List[AITrainingExample]:
        """Método auxiliar privado para processar dados carregados.
        
        Args:
            data: Dados JSON já carregados.
            
        Returns:
            Lista de exemplos de treinamento.
            
        Raises:
            FileProcessingError: Se os dados não estiverem em formato válido.
        """
        # Valida os dados antes de processá-los
        validation_result = validate_training_data(data)
        if not validation_result.is_valid:
            raise FileProcessingError(f"Dados de treinamento inválidos: {validation_result.error_message}")
        
        examples: List[AITrainingExample] = []
        for item in data:
            example = AITrainingExample(
                system_message=item.get("system_message", ""),
                user_message=item["user_message"],
                response=item["response"]
            )
            examples.append(example)
        
        return examples
    
    @staticmethod
    def create(source: Union[list, str, io.BytesIO]) -> 'AITrainingExampleCollection':
        """Cria uma coleção de exemplos a partir da fonte fornecida.
        
        Esta função detecta o tipo da fonte e executa a lógica adequada.
        
        Args:
            source: Fonte dos dados, que pode ser:
                - lista: Json com dados já carregados
                - str: caminho do arquivo
                - BytesIO: objeto de bytes em memória
            
        Returns:
            Nova instância de AITrainingFileCollection com os exemplos.
            
        Raises:
            TypeError: Quando o tipo de fonte não é suportado.
            FileProcessingError: Se os dados não estiverem em formato válido.
        """
        # Verifica o tipo da fonte e chama a lógica correspondente
        if isinstance(source, list):
            # Processa dados já carregados
            examples = AITrainingExampleCollection._process_data(source)
            return AITrainingExampleCollection(examples)
        
        elif isinstance(source, str):
            # Carrega dados de um arquivo
            if not os.path.exists(source):
                return AITrainingExampleCollection()
                
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    # Verifica se o arquivo está vazio
                    content = f.read()

                    if not content.strip() or content == "[]":
                        # Se o arquivo estiver vazio, retorna uma coleção vazia
                        return AITrainingExampleCollection()
                    
                    # O arquivo não está vazio, carrega o conteúdo como JSON
                    data = json.loads(content)
                
                examples = AITrainingExampleCollection._process_data(data)
                return AITrainingExampleCollection(examples)
                
            except FileProcessingError:
                # Repassa a exceção de validação
                raise
            except Exception as e:
                # Captura e converte outras exceções
                raise FileProcessingError(f"Erro ao carregar exemplos: {e}")
        
        elif isinstance(source, io.BytesIO):
            # Carrega dados de um BytesIO
            try:
                # Lê o conteúdo do BytesIO como string
                source.seek(0)
                content = source.read().decode('utf-8')
                data = json.loads(content)
                
                examples = AITrainingExampleCollection._process_data(data)
                return AITrainingExampleCollection(examples)
                
            except FileProcessingError:
                # Repassa a exceção de validação
                raise
            except Exception as e:
                # Captura e converte outras exceções
                raise FileProcessingError(f"Erro ao processar dados de exemplos: {e}")
        
        else:
            # Tipo não suportado
            raise TypeError(f"Tipo de fonte não suportado: {type(source)}")

@dataclass
class AITrainingCaptureConfig:
    """Dados de captura de treinamento.
    
    Args:
        id: Identificador da configuração.
        token_id: Identificador do token.
        ai_client_config_id: Configuração de IA associada.
        is_active: Define se está ativo.
        file: Coleção de arquivos de treinamento.
        create_at: Data de criação.
        last_activity: Última atividade.
    """
    id: int
    token_id: int
    ai_client_config_id: int
    is_active: bool
    file: AITrainingExampleCollection = field(default_factory=AITrainingExampleCollection)
    create_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> JSONDict:
        """Converte a configuração de captura de treinamento para um dicionário serializável em JSON.
        
        Returns:
            Dicionário com os atributos da configuração de captura de treinamento.
        """
        return {
            "id": self.id,
            "token_id": self.token_id,
            "ai_client_config_id": self.ai_client_config_id,
            "is_active": self.is_active,
            "file": self.file.to_dict(),
            "create_at": self.create_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }

# -----------------------------------------------------------------------------
# Tipos para Treinamento
# -----------------------------------------------------------------------------
@dataclass
class AITrainingFileData:
    """Dados de arquivo de treinamento.
    
    Args:
        id: Identificador do arquivo.
        user_id: Identificador do usuário.
        name: Nome do arquivo.
        uploaded_at: Data de upload.
        file: Coleção de arquivos de treinamento.
        file_size: Tamanho do arquivo.
        example_count: Quantidade de exemplos no arquivo.
    """
    user_id: int
    name: str
    id: int = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    file: AITrainingExampleCollection = field(default_factory=AITrainingExampleCollection)
    file_size: Optional[int] = 0
    example_count: Optional[int] = 0

AITrainingFileDataCollection = List[AITrainingFileData]

class AITrainingStatus(Enum):
    """Status de treinamento de modelo.
    
    Valores:
        NOT_STARTED: Treinamento não iniciado.
        IN_PROGRESS: Treinamento em andamento.
        COMPLETED: Treinamento concluído com sucesso.
        FAILED: Treinamento falhou.
        CANCELLED: Treinamento cancelado pelo usuário.
    """
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class AITrainingResponse:
    """Dados de job de treinamento.
    
    Args:
        job_id: Identificador externo.
        status: Status atual.
        model_name: Nome do modelo treinado.
        error: Erro ocorrido.
        completed_at: Data de conclusão.
        created_at: Data de criação.
        updated_at: Data de última atualização.
        progress: Progresso do treinamento (0.0 a 1.0).
    """
    job_id: str
    status: AITrainingStatus
    model_name: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0
