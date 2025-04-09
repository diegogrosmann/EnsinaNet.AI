"""
Tipos relacionados a operações de longa duração (Long-Running Operations - LRO).

Define estruturas de dados para representar operações que são executadas de forma
assíncrona e podem levar um tempo considerável para serem concluídas.
"""
import logging
from typing import Optional, Dict, Any, Generic
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from abc import ABC

from core.types.task import TaskDict

from .base import BaseEnum, DataModel, JSONDict, DataModelDict, TDataModel, TModel
from .errors import APPError, ErrorModel
from .status import EntityStatus

logger = logging.getLogger(__name__)

class OperationType(BaseEnum):
    """Tipos de operações de longa duração.
    
    Enumera os diferentes tipos de operações assíncronas que podem ser realizadas,
    permitindo categorizar e identificar o propósito de cada operação.
    
    Valores:
        COMPARISON: Operação de comparação entre documentos ou dados.
        TRAINING: Operação de treinamento de modelos.
    """
    COMPARISON = "comparison"
    TRAINING = "training"
    GENERIC = "generic"


class OperationResultDict(DataModelDict[TModel]):
    pass

@dataclass
class OperationData(DataModel, Generic[TDataModel], ABC):
    """Representa uma operação de longa duração.
    
    Implementa o padrão Long-Running Operation (LRO) para operações que podem
    levar tempo considerável para serem concluídas, permitindo que o cliente
    receba imediatamente um identificador e consulte o status posteriormente.
    
    Args:
        user_id: ID do usuário que iniciou a operação.
        user_token_id: ID do token usado para iniciar a operação.
        operation_id: Identificador único da operação.
        created_at: Momento de criação da operação.
        updated_at: Momento da última atualização da operação.
        meta: Metadados adicionais da operação.
        expiration: Momento em que a operação expira.
        operation_type: Tipo de operação (ex: "comparison", "training").
        tasks: Dicionário de tarefas associadas a esta operação.
    """
    
    user_id: int
    user_token_id: str
    
    operation_type: OperationType
    operation_id: str = None

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    meta: JSONDict = field(default_factory=dict)
    expiration: Optional[datetime] = None
    tasks: TaskDict = field(default_factory=TaskDict)
    
    def __post_init__(self):
        """Inicializa valores e valida o objeto após a criação."""
        if not self.expiration:
            # Default de 24 horas de expiração
            self.expiration = datetime.now() + timedelta(hours=24)
            
        # Inicializa o dicionário de tarefas se não foi fornecido
        if not self.tasks:
            self.tasks = TaskDict()
    
    def get_status(self) -> EntityStatus:
        """Retorna o status consolidado baseado nas tarefas associadas.
        
        Returns:
            EntityStatus: Status atual da operação.
        """
        # Se não houver tarefas, retorna o status inicial
        if not hasattr(self.tasks, '_items') or not self.tasks._items:
            return EntityStatus.NOT_STARTED
            
        # Determinar status consolidado baseado nas tarefas
        has_failed = any(
            task.status == EntityStatus.FAILED
            for task in self.tasks._items.values()
        )
        has_pending = any(
            task.status == EntityStatus.PENDING
            for task in self.tasks._items.values()
        )
        has_processing = any(
            task.status == EntityStatus.PROCESSING
            for task in self.tasks._items.values()
        )
        all_completed = all(
            task.status == EntityStatus.COMPLETED
            for task in self.tasks._items.values()
        )
        
        # Determinar o status consolidado
        if has_failed:
            return EntityStatus.FAILED
        elif has_pending or has_processing:
            return EntityStatus.PROCESSING
        elif all_completed:
            return EntityStatus.COMPLETED
        else:
            return EntityStatus.PROCESSING
    
    def get_progress(self) -> float:
        """Retorna o progresso médio baseado nas tarefas associadas.
        
        Returns:
            float: Progresso da operação entre 0.0 e 1.0.
        """
        # Se não houver tarefas, retorna 0
        if not hasattr(self.tasks, '_items') or not self.tasks._items:
            return 0.0
            
        # Calcular progresso médio
        task_count = len(self.tasks._items)
        if task_count == 0:
            return 0.0
            
        total_progress = sum(
            task.progress / 100.0 if task.progress > 1.0 else task.progress
            for task in self.tasks._items.values()
        )
        return total_progress / task_count
    
    def get_complete_at(self) -> Optional[datetime]:
        """Retorna a data de conclusão da última tarefa concluída.
        
        Returns:
            Optional[datetime]: Data de conclusão da operação ou None se não estiver concluída.
        """
        # Se não houver tarefas ou não estiverem todas concluídas, retorna None
        if not hasattr(self.tasks, '_items') or not self.tasks._items:
            return None
            
        # Verificar se todas as tarefas estão concluídas
        if not all(task.status == EntityStatus.COMPLETED for task in self.tasks._items.values()):
            return None
            
        # Obter a data de atualização mais recente entre todas as tarefas concluídas
        completed_tasks = [
            task for task in self.tasks._items.values() 
            if task.status == EntityStatus.COMPLETED
        ]
        
        if not completed_tasks:
            return None
            
        return max(task.updated_at for task in completed_tasks)
    
    def get_result(self) -> Optional[OperationResultDict]:
        """Retorna o resultado consolidado das tarefas concluídas.
        
        Returns:
            OperationResultDict: Resultados consolidados de todas as tarefas concluídas.
        """
        # Se não houver tarefas, retorna None
        if not hasattr(self.tasks, '_items') or not self.tasks._items:
            return None
        
        # Extrair os resultados das tarefas concluídas
        task_results = {
            task_id: task.result
            for task_id, task in self.tasks._items.items()
            if task.status == EntityStatus.COMPLETED and hasattr(task, 'result') and task.result
        }
        
        if not task_results:
            return None
            
        return OperationResultDict(items=task_results)
    
    def get_error(self) -> Optional[ErrorModel]:
        """Retorna um erro consolidado baseado em todas as tarefas com erro.
        
        Returns:
            ErrorModel: Erro consolidado ou None se não houver erros.
        """
        # Se não houver tarefas, retorna None
        if not hasattr(self.tasks, '_items') or not self.tasks._items:
            return None
            
        # Coletar erros de tarefas falhas
        errors = []
        for task_id, task in self.tasks._items.items():
            if task.status == EntityStatus.FAILED and task.error:
                error_info = {
                    "task_id": task_id,
                    "message": str(task.error)
                }
                if hasattr(task.error, 'to_dict'):
                    error_info = task.error.to_dict()
                    error_info["task_id"] = task_id
                errors.append(error_info)
                
        if not errors:
            return None
            
        # Criar um ErrorModel consolidado
        return APPError(
            message=f"Falha em {len(errors)} tarefa(s) associadas",
            additional_data={"tasks_with_errors": errors}
        )
    
    def cancel(self) -> None:
        """Cancela a operação em andamento atualizando todas as tasks para cancelado."""
        # Itera por todas as tasks associadas e atualiza seu status para CANCELLED
        for task in self.tasks._items.values():
            task.update_status(EntityStatus.CANCELLED, "Operação cancelada pelo usuário")
        logger.info(f"Todas as tasks da OperationData {self.operation_id} foram canceladas")
    
    def set_failure(self, error_msg: str) -> None:
        """Marca todas as tasks associadas como falha e insere a mensagem de erro."""
        # Itera por todas as tasks associadas e define a falha com a mensagem de erro
        for task in self.tasks._items.values():
            task.set_failure(error_msg)
        logger.error(f"OperationData {self.operation_id} configurada com falha: {error_msg}")
    
    def is_done(self) -> bool:
        """Verifica se a operação está finalizada (concluída, falha ou cancelada).
        
        Returns:
            bool: True se a operação estiver finalizada.
        """
        current_status = self.get_status()
        return current_status in (EntityStatus.COMPLETED, EntityStatus.FAILED, 
                               EntityStatus.CANCELLED, EntityStatus.EXPIRED)
    
    def is_expired(self) -> bool:
        """Verifica se a operação está expirada.
        
        Returns:
            bool: True se a operação estiver expirada.
        """
        return datetime.now() > self.expiration if self.expiration else False
    
    def to_dict(self) -> JSONDict:
        """Converte a operação em um dicionário JSON, incluindo campos calculados.
        
        Returns:
            JSONDict: Representação em dicionário da operação.
        """
        # Primeiro obtém o dicionário base
        result = super().to_dict()
        
        # Adiciona campos calculados
        result["status"] = str(self.get_status())
        result["progress"] = self.get_progress()
        
        # Adiciona completed_at se disponível
        completed_at = self.get_complete_at()
        if completed_at:
            result["completed_at"] = completed_at.isoformat()
        
        # Adiciona erro se existir
        error = self.get_error()
        if error:
            result["error"] = error.to_dict() if hasattr(error, 'to_dict') else {"message": str(error)}
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OperationData':
        """Cria uma instância de OperationData a partir de um dicionário.
        
        Remove os campos calculados que são adicionados pelo método to_dict().
        
        Args:
            data: Dicionário com dados serializado.
            
        Returns:
            Nova instância de OperationData.
        """
        # Remover campos calculados que não devem ser passados para o construtor
        data_copy = data.copy()
        data_copy.pop('status', None)
        data_copy.pop('progress', None)
        data_copy.pop('completed_at', None)
        data_copy.pop('error', None)
        
        # Delega o resto para a implementação da classe pai
        return super().from_dict(data_copy)
    
    def get_summary(self) -> dict:
        """
        Retorna um resumo da operação contendo:
        - Dados principais (operation_id, user_id, etc.) com datas em formato string.
        - Dados estatísticos (status, progresso e tarefas).
        - Resultados (convertidos recursivamente em dict, com datas em string e erros reduzidos às mensagens).
        - Em caso de erro consolidado, retorna apenas as mensagens de erros.
        """
        # 1) Verifica se há algum erro consolidado na operação:
        error = self.get_error()
        if error:
            # Coleta somente as mensagens de erro, ignorando a classe ou detalhes
            tasks_with_errors = error.additional_data.get("tasks_with_errors", []) if error.additional_data else []
            error_messages = []
            for err_info in tasks_with_errors:
                # Se no dicionário houver "message", extraímos somente ela
                if "message" in err_info:
                    error_messages.append(err_info["message"])

            return {
                "operation_id": self.operation_id,
                "status": str(self.get_status()),
                "errors": error_messages
            }

        # 2) Se não há erros, montamos o resumo normal.

        # Função auxiliar para conversão recursiva de datas e erros nos resultados
        def _serialize_result(obj):
            """
            Transforma:
            - Qualquer datetime/date em string (isoformat).
            - Dicionários/listas recursivamente.
            - Caso encontre algum "erro" (ErrorModel ou similar), retorna apenas a mensagem.
            """
            if isinstance(obj, (datetime, date)):
                # Converte datas para string
                return obj.isoformat()
            elif isinstance(obj, dict):
                # Se for um dicionário, processa cada chave recursivamente
                new_dict = {}
                for k, v in obj.items():
                    # Se a chave parecer "error", guarde só a mensagem (caso seja um dicionário de erro)
                    if k.lower() == "error":
                        if isinstance(v, dict) and "message" in v:
                            new_dict[k] = v["message"]
                        else:
                            # Se vier algo fora do padrão, apenas serializa
                            new_dict[k] = _serialize_result(v)
                    else:
                        new_dict[k] = _serialize_result(v)
                return new_dict
            elif isinstance(obj, list):
                return [_serialize_result(item) for item in obj]
            else:
                # Para qualquer outro tipo, retorna diretamente
                return obj

        status = self.get_status()
        progress = self.get_progress()

        # Resumo das tasks
        task_count = len(self.tasks._items) if self.tasks and self.tasks._items else 0
        tasks_summary = {
            "count": task_count,
            "completed": sum(
                1 for t in self.tasks._items.values() 
                if t.status == EntityStatus.COMPLETED
            ) if task_count else 0,
            "failed": sum(
                1 for t in self.tasks._items.values()
                if t.status == EntityStatus.FAILED
            ) if task_count else 0,
            "in_progress": sum(
                1 for t in self.tasks._items.values()
                if t.status in (EntityStatus.PENDING, EntityStatus.PROCESSING)
            ) if task_count else 0
        }

        # Pega o resultado cru (que pode ter datas e/ou erros embutidos)
        raw_results = self.get_result()

        
        # Converte o resultado para algo serializável (datetimes -> str, erros -> mensagem, etc.)
        serialized_results = _serialize_result(raw_results) if raw_results else None

        return {
            "operation_id": self.operation_id,
            "operation_type": str(self.operation_type),
            "user_id": self.user_id,
            "user_token_id": self.user_token_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expiration": self.expiration.isoformat() if self.expiration else None,
            "status": str(status),
            "progress": progress,
            "tasks_summary": tasks_summary,
            "results": serialized_results.to_dict() if serialized_results is not None else None
        }

