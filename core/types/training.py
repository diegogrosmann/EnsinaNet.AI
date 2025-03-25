"""
Tipos relacionados ao treinamento e captura de exemplos para IA.

Define estruturas de dados para gerenciar exemplos de treinamento,
incluindo coleções de exemplos e configurações de captura de dados.
"""
import io
import json
import os
import logging
from typing import List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from .messaging import AIMessage
from .base import JSONDict
from .validation import ValidationResult
from .task import TaskStatus
from core.exceptions import FileProcessingError, TrainingError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para Captura de Exemplos
# -----------------------------------------------------------------------------
@dataclass
class AITrainingExample(AIMessage):
    """Exemplo de treinamento.
    
    Representa um exemplo completo para treinamento de IA,
    incluindo mensagens de sistema, usuário e a resposta esperada.
    
    Args:
        response: Resposta esperada para as mensagens.
    """
    response: str
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        super().__post_init__()
        if not self.response:
            logger.warning("AITrainingExample criado com resposta vazia")
    
    def to_dict(self) -> JSONDict:
        """Converte o exemplo de treinamento para um dicionário serializável em JSON.
        
        Returns:
            JSONDict: Dicionário com os atributos do exemplo de treinamento.
        """
        logger.debug("Convertendo exemplo de treinamento para dicionário")
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
        examples: Lista de exemplos de treinamento.
    """
    examples: List[AITrainingExample] = field(default_factory=list)
    
    def __post_init__(self):
        """Inicializa a coleção de exemplos."""
        logger.debug(f"Criada coleção de exemplos de treinamento com {len(self.examples)} exemplos")
    
    def to_dict(self) -> List[JSONDict]:
        """Converte a coleção de exemplos de treinamento em formato de dicionário.
        
        Returns:
            List[JSONDict]: Lista de dicionários representando os exemplos de treinamento.
        """
        logger.debug(f"Convertendo coleção de {len(self.examples)} exemplos para dicionário")
        return [example.to_dict() for example in self.examples]
    
    @staticmethod
    def _process_data(data) -> List[AITrainingExample]:
        """Método auxiliar privado para processar dados carregados.
        
        Args:
            data: Dados JSON já carregados.
            
        Returns:
            List[AITrainingExample]: Lista de exemplos de treinamento.
            
        Raises:
            FileProcessingError: Se os dados não estiverem em formato válido.
        """
        try:
            # Importação feita aqui para evitar dependência cíclica
            from core.validators import validate_training_data
            
            # Valida os dados antes de processá-los
            validation_result = validate_training_data(data)
            if not validation_result.is_valid:
                logger.error(f"Dados de treinamento inválidos: {validation_result.error_message}")
                raise FileProcessingError(f"Dados de treinamento inválidos: {validation_result.error_message}")
            
            examples: List[AITrainingExample] = []
            for item in data:
                example = AITrainingExample(
                    system_message=item.get("system_message", ""),
                    user_message=item["user_message"],
                    response=item["response"]
                )
                examples.append(example)
            
            logger.info(f"Processados {len(examples)} exemplos de treinamento com sucesso")
            return examples
        except FileProcessingError:
            # Repassa a exceção já formatada
            raise
        except Exception as e:
            logger.error(f"Erro ao processar dados de treinamento: {str(e)}", exc_info=True)
            raise FileProcessingError(f"Erro ao processar dados de treinamento: {str(e)}")
    
    @classmethod
    def create(cls, source: Union[list, str, io.BytesIO]) -> 'AITrainingExampleCollection':
        """Cria uma coleção de exemplos a partir da fonte fornecida.
        
        Esta função detecta o tipo da fonte e executa a lógica adequada.
        
        Args:
            source: Fonte dos dados, que pode ser:
                - lista: Json com dados já carregados
                - str: caminho do arquivo
                - BytesIO: objeto de bytes em memória
            
        Returns:
            AITrainingExampleCollection: Nova instância com os exemplos.
            
        Raises:
            TypeError: Quando o tipo de fonte não é suportado.
            FileProcessingError: Se os dados não estiverem em formato válido.
        """
        logger.info(f"Criando coleção de exemplos de treinamento a partir de {type(source).__name__}")
        
        # Verifica o tipo da fonte e chama a lógica correspondente
        if isinstance(source, list):
            # Processa dados já carregados
            try:
                examples = AITrainingExampleCollection._process_data(source)
                return AITrainingExampleCollection(examples)
            except Exception as e:
                logger.error(f"Erro ao criar coleção a partir de lista: {str(e)}", exc_info=True)
                raise
        
        elif isinstance(source, str):
            # Carrega dados de um arquivo
            logger.debug(f"Tentando carregar exemplos do arquivo: {source}")
            if not os.path.exists(source):
                logger.warning(f"Arquivo não encontrado: {source}. Retornando coleção vazia.")
                return AITrainingExampleCollection()
                
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    # Verifica se o arquivo está vazio
                    content = f.read()

                    if not content.strip() or content == "[]":
                        # Se o arquivo estiver vazio, retorna uma coleção vazia
                        logger.info(f"Arquivo vazio ou com lista vazia: {source}")
                        return AITrainingExampleCollection()
                    
                    # O arquivo não está vazio, carrega o conteúdo como JSON
                    data = json.loads(content)
                
                examples = AITrainingExampleCollection._process_data(data)
                logger.info(f"Carregados {len(examples)} exemplos do arquivo: {source}")
                return AITrainingExampleCollection(examples)
                
            except FileProcessingError:
                # Repassa a exceção de validação
                raise
            except json.JSONDecodeError as e:
                logger.error(f"Erro de formato JSON no arquivo {source}: {str(e)}", exc_info=True)
                raise FileProcessingError(f"Formato JSON inválido no arquivo: {str(e)}")
            except Exception as e:
                # Captura e converte outras exceções
                logger.error(f"Erro ao carregar exemplos: {str(e)}", exc_info=True)
                raise FileProcessingError(f"Erro ao carregar exemplos: {str(e)}")
        
        elif isinstance(source, io.BytesIO):
            # Carrega dados de um BytesIO
            try:
                # Lê o conteúdo do BytesIO como string
                source.seek(0)
                content = source.read().decode('utf-8')
                
                if not content.strip() or content == "[]":
                    logger.info("BytesIO vazio ou com lista vazia")
                    return AITrainingExampleCollection()
                
                data = json.loads(content)
                
                examples = AITrainingExampleCollection._process_data(data)
                logger.info(f"Carregados {len(examples)} exemplos de BytesIO")
                return AITrainingExampleCollection(examples)
                
            except FileProcessingError:
                # Repassa a exceção de validação
                raise
            except json.JSONDecodeError as e:
                logger.error(f"Erro de formato JSON no BytesIO: {str(e)}", exc_info=True)
                raise FileProcessingError(f"Formato JSON inválido: {str(e)}")
            except Exception as e:
                # Captura e converte outras exceções
                logger.error(f"Erro ao processar dados de exemplos: {str(e)}", exc_info=True)
                raise FileProcessingError(f"Erro ao processar dados de exemplos: {str(e)}")
        
        else:
            # Tipo não suportado
            error_msg = f"Tipo de fonte não suportado: {type(source)}"
            logger.error(error_msg)
            raise TypeError(error_msg)

@dataclass
class AITrainingCaptureConfig:
    """Dados de captura de treinamento.
    
    Representa uma configuração para captura de exemplos de treinamento,
    incluindo o token de acesso e o cliente de IA associados.
    
    Args:
        id: Identificador único da configuração.
        token_id: Identificador do token de acesso.
        ai_client_config_id: Identificador da configuração de IA associada.
        is_active: Define se a captura está ativa.
        file: Coleção de exemplos de treinamento.
        create_at: Data de criação da configuração.
        last_activity: Data da última atividade registrada.
    """
    id: int
    token_id: int
    ai_client_config_id: int
    is_active: bool
    file: AITrainingExampleCollection = field(default_factory=AITrainingExampleCollection)
    create_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        logger.debug(f"Configuração de captura criada: ID {self.id}, ativa: {self.is_active}")
    
    def to_dict(self) -> JSONDict:
        """Converte a configuração de captura de treinamento para um dicionário serializável em JSON.
        
        Returns:
            JSONDict: Dicionário com os atributos da configuração de captura de treinamento.
        """
        logger.debug(f"Convertendo configuração de captura ID {self.id} para dicionário")
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
class TrainingStatus(Enum):
    """Status de treinamento de modelo.
    
    Representa os possíveis estados de um job de treinamento de modelo,
    permitindo rastrear seu progresso desde o início até a conclusão ou falha.
    
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
class AITrainingFileData:
    """Dados de arquivo de treinamento.
    
    Representa um arquivo de dados de treinamento enviado pelo usuário
    e seus metadados associados.
    
    Args:
        user_id: Identificador do usuário proprietário.
        name: Nome do arquivo.
        id: Identificador único do arquivo (opcional).
        uploaded_at: Data de envio do arquivo.
        file: Coleção de exemplos de treinamento.
        file_size: Tamanho do arquivo em bytes.
        example_count: Quantidade de exemplos no arquivo.
    """
    user_id: int
    name: str
    id: Optional[int] = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    file: AITrainingExampleCollection = field(default_factory=AITrainingExampleCollection)
    file_size: Optional[int] = 0
    example_count: Optional[int] = 0

    def __post_init__(self):
        """Inicializa e valida o objeto após criação."""
        if self.file and not self.example_count:
            self.example_count = len(self.file.examples)
        logger.debug(f"AITrainingFileData criado: {self.name} ({self.example_count} exemplos)")
    
    def to_dict(self) -> JSONDict:
        """Converte os dados do arquivo para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os dados do arquivo de treinamento.
        """
        result = {
            "user_id": self.user_id,
            "name": self.name,
            "uploaded_at": self.uploaded_at.isoformat(),
            "file_size": self.file_size,
            "example_count": self.example_count
        }
        
        if self.id is not None:
            result["id"] = self.id
            
        # A conversão da coleção de exemplos é feita separadamente
        # para evitar sobrecarga de memória em arquivos muito grandes
        
        return result

AITrainingFileDataCollection = List[AITrainingFileData]
"""Coleção de arquivos de dados de treinamento."""

@dataclass
class AITrainingResponse:
    """Dados de job de treinamento.
    
    Representa o estado atual de um job de treinamento em andamento
    ou concluído, incluindo informações sobre progresso e resultado.
    
    Args:
        job_id: Identificador externo do job de treinamento.
        status: Status atual do treinamento.
        model_name: Nome do modelo resultante (se concluído).
        error: Mensagem de erro (se falhou).
        completed_at: Data de conclusão do treinamento.
        created_at: Data de criação do job.
        updated_at: Data da última atualização de status.
        progress: Progresso do treinamento (0.0 a 1.0).
    """
    job_id: str
    status: TrainingStatus
    model_name: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0

    def __post_init__(self):
        """Inicializa e valida o objeto após criação."""
        if self.status == TrainingStatus.COMPLETED and not self.model_name:
            logger.warning(f"Job {self.job_id} marcado como COMPLETED sem model_name definido")
            
        if self.status == TrainingStatus.FAILED and not self.error:
            logger.warning(f"Job {self.job_id} marcado como FAILED sem mensagem de erro")
            
        if self.progress < 0.0 or self.progress > 1.0:
            logger.warning(f"Job {self.job_id} com progresso inválido: {self.progress}")
            self.progress = max(0.0, min(1.0, self.progress))  # Normaliza entre 0.0 e 1.0
            
        logger.info(f"AITrainingResponse: job {self.job_id} com status {self.status.value} "
                  f"e progresso {self.progress:.1%}")
    
    def to_dict(self) -> JSONDict:
        """Converte os dados do job para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os dados do job de treinamento.
        """
        result = {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
        if self.model_name:
            result["model_name"] = self.model_name
            
        if self.error:
            result["error"] = self.error
            
        if self.completed_at:
            result["completed_at"] = self.completed_at.isoformat()
            
        return result
