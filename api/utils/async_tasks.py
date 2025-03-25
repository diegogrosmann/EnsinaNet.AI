"""
Utilitários para gerenciamento de tarefas assíncronas.

Fornece funções para armazenar, recuperar e atualizar o estado
de tarefas que estão sendo processadas de forma assíncrona.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from core.exceptions import ApplicationError
from core.types.async_task import AsyncTask, AsyncTaskStatus

logger = logging.getLogger(__name__)

def submit_task(task: AsyncTask, ttl: int = 86400) -> None:
    """Armazena uma nova tarefa assíncrona no banco de dados.
    
    Args:
        task: Tarefa a ser armazenada
        ttl: Tempo de vida da tarefa em segundos (não utilizado no BD)
        
    Raises:
        ApplicationError: Se ocorrer erro ao armazenar a tarefa
    """
    from api.models import AsyncTaskRecord
    
    try:
        # Mapeamento de status
        status_map = {
            AsyncTaskStatus.PENDING: "pending",
            AsyncTaskStatus.PROCESSING: "processing",
            AsyncTaskStatus.COMPLETED: "completed",
            AsyncTaskStatus.FAILED: "failed",
            AsyncTaskStatus.EXPIRED: "expired"
        }
        
        # Cria registro no banco de dados
        AsyncTaskRecord.objects.create(
            task_id=task.task_id,
            status=status_map.get(task.status, "pending"),
            user_id=task.user_id,
            user_token_id=task.user_token_id,
            input_data=task.input_data,
            result=task.result,
            error=task.error
        )
        
        logger.info(f"Tarefa {task.task_id} armazenada no banco de dados")
    except Exception as e:
        logger.error(f"Erro ao submeter tarefa {task.task_id}: {str(e)}", exc_info=True)
        raise ApplicationError(f"Erro ao registrar tarefa: {str(e)}")

def get_task(task_id: str) -> Optional[AsyncTask]:
    """Recupera uma tarefa do banco de dados pelo seu identificador.
    
    Args:
        task_id: Identificador único da tarefa
        
    Returns:
        AsyncTask se encontrada, None caso contrário
        
    Raises:
        ApplicationError: Se ocorrer erro ao recuperar a tarefa
    """
    from api.models import AsyncTaskRecord
    
    try:
        try:
            record = AsyncTaskRecord.objects.get(task_id=task_id)
            task = record.to_core_type()
            return task
        except AsyncTaskRecord.DoesNotExist:
            logger.warning(f"Tarefa não encontrada: {task_id}")
            return None
    except Exception as e:
        logger.error(f"Erro ao recuperar tarefa {task_id}: {str(e)}", exc_info=True)
        raise ApplicationError(f"Erro ao recuperar tarefa: {str(e)}")

def update_task(task: AsyncTask, ttl: Optional[int] = None) -> None:
    """Atualiza o estado de uma tarefa no banco de dados.
    
    Args:
        task: Tarefa com o estado atualizado
        ttl: Tempo de vida em segundos (ignorado nesta implementação)
        
    Raises:
        ApplicationError: Se ocorrer erro ao atualizar a tarefa
    """
    from api.models import AsyncTaskRecord
    
    try:
        # Mapeamento de status
        status_map = {
            AsyncTaskStatus.PENDING: "pending",
            AsyncTaskStatus.PROCESSING: "processing", 
            AsyncTaskStatus.COMPLETED: "completed",
            AsyncTaskStatus.FAILED: "failed",
            AsyncTaskStatus.EXPIRED: "expired"
        }
        
        record = AsyncTaskRecord.objects.get(task_id=task.task_id)
        record.status = status_map.get(task.status, record.status)
        record.result = task.result
        record.error = task.error
        record.save()
        
        logger.info(f"Tarefa {task.task_id} atualizada no banco de dados com status {task.status}")
    except AsyncTaskRecord.DoesNotExist:
        logger.error(f"Tentativa de atualizar tarefa inexistente: {task.task_id}")
        raise ApplicationError(f"Tarefa {task.task_id} não encontrada")
    except Exception as e:
        logger.error(f"Erro ao atualizar tarefa {task.task_id}: {str(e)}", exc_info=True)
        raise ApplicationError(f"Erro ao atualizar tarefa: {str(e)}")

def store_task_result(
    task_id: str, 
    result: Optional[Dict[str, Any]] = None, 
    error: Optional[str] = None
) -> None:
    """Armazena o resultado de uma tarefa ou marca como falha.
    
    Args:
        task_id: Identificador da tarefa
        result: Resultado da tarefa (se bem-sucedida)
        error: Mensagem de erro (se falhou)
        
    Raises:
        ApplicationError: Se ocorrer erro ao processar a atualização
    """
    from api.models import AsyncTaskRecord
    
    try:
        # Recupera a tarefa
        try:
            record = AsyncTaskRecord.objects.get(task_id=task_id)
        except AsyncTaskRecord.DoesNotExist:
            logger.error(f"Tentativa de armazenar resultado para tarefa inexistente: {task_id}")
            raise ApplicationError(f"Tarefa {task_id} não encontrada")
        
        # Atualiza o status e os dados
        if error:
            record.status = "failed"
            record.error = error
            logger.error(f"Tarefa {task_id} marcada como falha: {error}")
        else:
            record.status = "completed"
            record.result = result
            logger.info(f"Tarefa {task_id} concluída com sucesso")
        
        # Salva as alterações
        record.save()
            
    except ApplicationError:
        # Repassa a exceção
        raise
    except Exception as e:
        logger.error(f"Erro ao armazenar resultado da tarefa {task_id}: {str(e)}", exc_info=True)
        raise ApplicationError(f"Erro ao processar resultado da tarefa: {str(e)}")
