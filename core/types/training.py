"""
Tipos relacionados ao treinamento e captura de exemplos para IA.

Define estruturas de dados para gerenciar exemplos de treinamento,
incluindo coleções de exemplos e configurações de captura de dados.
"""
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.exceptions import CoreValueException

from core.types.ai import AIExampleDict
from core.types.base import DataModel, JSONDict, TDataModel
from core.types.status import EntityStatus
from core.types.task import QueueableTask
from core.types.operation import OperationData, OperationType

logger = logging.getLogger(__name__)


@dataclass
class TrainingCaptureConfig(DataModel):
    """Dados de captura de treinamento.
    
    Representa uma configuração para captura de exemplos de treinamento,
    incluindo o token de acesso e o cliente de IA associados.
    
    Args:
        id: Identificador único da configuração.
        token_id: Identificador do token de acesso.
        ai_client_config_id: Identificador da configuração de IA associada.
        is_active: Define se a captura está ativa.
        data: Coleção de exemplos de treinamento.
        create_at: Data de criação da configuração.
        last_activity: Data da última atividade registrada.
    """
    id: int
    token_id: int
    ai_client_config_id: int
    is_active: bool
    data: AIExampleDict = field(default_factory=lambda: AIExampleDict({}))
    create_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        logger.debug(f"Configuração de captura criada: ID {self.id}, ativa: {self.is_active}")
        if not isinstance(self.data, AIExampleDict):
            raise CoreValueException(
                "O campo 'data' deve ser uma instância de AIExampleDict",
                field="data",
                type_name="TrainingCaptureConfig"
            )


# -----------------------------------------------------------------------------
# Tipos para Resposta
# -----------------------------------------------------------------------------
@dataclass
class TrainingResponse(DataModel):
    """Resposta de operações de treinamento.
    
    Representa o resultado de uma operação de treinamento, incluindo status,
    progresso e eventuais erros.
    
    Attributes:
        job_id: Identificador único do job de treinamento
        status: Status atual do treinamento (EntityStatus)
        model_name: Nome do modelo resultante do treinamento (None se em progresso)
        error: Mensagem de erro (se aplicável)
        completed_at: Data/hora de conclusão (None se em progresso)
        created_at: Data/hora de criação
        updated_at: Data/hora da última atualização
        progress: Progresso do treinamento (0.0 a 1.0)
    """
    job_id: str
    status: EntityStatus
    model_name: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    progress: float = 0.0
    
    @property
    def is_complete(self) -> bool:
        """Verifica se o treinamento está concluído.
        
        Returns:
            bool: True se o status for COMPLETED.
        """
        return self.status == EntityStatus.COMPLETED
    
    @property
    def is_failed(self) -> bool:
        """Verifica se o treinamento falhou.
        
        Returns:
            bool: True se o status for FAILED.
        """
        return self.status == EntityStatus.FAILED
    
    @property
    def is_in_progress(self) -> bool:
        """Verifica se o treinamento está em andamento.
        
        Returns:
            bool: True se o status for IN_PROGRESS.
        """
        return self.status == EntityStatus.IN_PROGRESS


@dataclass
class TrainingTask(QueueableTask):
    """Tarefa assíncrona específica para treinamento de IA.
    
    Especializa QueueableTask para o caso específico de treinamento de modelos de IA,
    com métodos e propriedades específicas para este tipo de operação.
    
    Attributes:
        training_data (AIExampleDict): Exemplos de treinamento para o modelo.
        model_name (str): Nome do modelo a ser treinado ou fine-tuned.
        ai_client_config_id (int): ID da configuração da IA a ser utilizada.
    """
    training_data: AIExampleDict = field(default_factory=lambda: AIExampleDict({}))
    model_name: str = None
    ai_client_config_id: int = None
    
    def __post_init__(self):
        """Inicializa dados específicos para tarefa de treinamento."""
        super().__post_init__()
        
        # Validar que os parâmetros obrigatórios foram fornecidos
        if not self.training_data:
            raise CoreValueException(
                "Dados de treinamento são obrigatórios",
                field="training_data", 
                type_name="TrainingTask"
            )
            
        if not self.model_name:
            raise CoreValueException(
                "Nome do modelo é obrigatório",
                field="model_name", 
                type_name="TrainingTask"
            )
            
        if not self.ai_client_config_id:
            raise CoreValueException(
                "ID de configuração da IA é obrigatório",
                field="ai_client_config_id", 
                type_name="TrainingTask"
            )
            
        if self.training_data:
            self.input_data = self.training_data
            
        if not isinstance(self.training_data, AIExampleDict):
            raise CoreValueException(
                "O campo 'training_data' deve ser uma instância de AIExampleDict",
                field="training_data",
                type_name="TrainingTask"
            )
            
        # Calcula estatísticas da tarefa
        if hasattr(self.training_data, 'items'):
            example_count = len(self.training_data.items)
            logger.info(f"TrainingTask {self.task_id} criada com {example_count} exemplos para o modelo {self.model_name}")
    
    @property
    def example_count(self) -> int:
        """Retorna o número de exemplos no conjunto de treinamento.
        
        Returns:
            int: Número de exemplos no conjunto de treinamento.
        """
        if not hasattr(self.training_data, 'items'):
            return 0
        return len(self.training_data.items)
    
    @property
    def is_large_task(self) -> bool:
        """Verifica se é uma tarefa grande que deve ser processada com prioridade baixa.
        
        Returns:
            bool: True se for uma tarefa grande (muitos exemplos de treinamento).
        """
        return self.example_count > 100
    
    def get_summary(self) -> JSONDict:
        """Retorna um resumo da tarefa de treinamento.
        
        Returns:
            JSONDict: Resumo com informações principais da tarefa.
        """
        base_dict = self.to_dict()
        base_dict["model_name"] = self.model_name
        base_dict["ai_client_config_id"] = self.ai_client_config_id
        base_dict["example_count"] = self.example_count
        base_dict["is_large_task"] = self.is_large_task
        
        # Remove dados completos de entrada e resultado para economizar espaço
        if "input_data" in base_dict:
            del base_dict["input_data"]
            
        # Em vez do resultado completo, fornecer apenas informações básicas
        if self.status == EntityStatus.COMPLETED and self.result is not None:
            # Extrair dados do DataModelDict
            result_dict = self.result.to_dict() if hasattr(self.result, 'to_dict') else {}
            
            # Prepara um resumo do resultado
            base_dict["result_summary"] = {
                "model_id": result_dict.get("model_id", ""),
                "training_status": result_dict.get("status", ""),
                "created_at": result_dict.get("created_at", ""),
                "examples_used": self.example_count
            }
            
            if "result" in base_dict:
                del base_dict["result"]
                
        return base_dict


class TrainingJob(OperationData):
    """Job de treinamento que executa a lógica de treinamento de modelos de IA.
    
    Representa uma operação completa de treinamento, encapsulando uma ou mais
    tarefas de treinamento relacionadas.
    """

    @staticmethod
    def __operation_type__() -> OperationType:
        """Retorna o tipo de operação.
        
        Returns:
            OperationType: Tipo da operação (TRAINING).
        """
        return OperationType.TRAINING
    
    @staticmethod
    def __response_type__() -> TDataModel:
        """Retorna o tipo de resposta esperado.
        
        Returns:
            TDataModel: Tipo da resposta esperada.
        """
        return AIExampleDict

    @classmethod
    def from_async_tasks(cls, tasks: List[TrainingTask]) -> 'TrainingJob':
        """Converte uma lista de TrainingTask para TrainingJob.

        Args:
            tasks: Lista de TrainingTask a serem convertidas.

        Returns:
            TrainingJob: Nova operação baseada nas tasks.
            
        Raises:
            CoreValueException: Se a lista de tasks estiver vazia.
        """
        from core.exceptions import CoreValueException
        
        if not tasks:
            raise CoreValueException("Lista de tasks vazia")
        
        trainingJob = super().from_async_tasks(tasks)
        # Criar o dicionário meta a partir da primeira task
        trainingJob.meta["model_name"] = tasks[0].model_name
        trainingJob.meta["example_count"] = tasks[0].example_count

        return trainingJob

