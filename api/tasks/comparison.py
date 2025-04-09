"""
Tasks Celery para processamento assíncrono da API.

Define tarefas que serão processadas em segundo plano pelo Celery,
como comparações assíncronas e outras operações de longa duração.
"""
import logging

from celery import shared_task

from core.types import (
    EntityStatus,
    JSONDict
)
from core.models import Operation
from core.types.comparison import ComparisonJob
from core.types.operation import OperationData

# Modificação do logger para usar o namespace que direciona para tasks.log
logger = logging.getLogger('ai_config.tasks')

@shared_task(
    bind=True, 
    name="process_comparison_job",
    max_retries=3,
    default_retry_delay=300
)
def process_comparison_job(self, operation_id: str) -> JSONDict:
    """Processa um job de comparação assíncrona em segundo plano.
    
    Args:
        operation_id: Identificador único da operação (job).
        
    Returns:
        JSONDict contendo informações sobre o processamento.
        
    Raises:
        Exception: Em caso de falha no processamento.
    """
    
    logger.info(f"[JOB:{operation_id}] Iniciando processamento de job de comparação")
    
    try:
        from api.service.comparator import execute_comparison
        # Recupera a operação do banco de dados
        operation = Operation.objects.get(operation_id=operation_id)
        job = operation.to_operation_data()
        
        if not isinstance(job, OperationData):
            error_msg = f"Job de comparação não encontrado ou inválido: {operation_id}"
            logger.error(f"[JOB:{operation_id}] {error_msg}")
            return {"success": False, "error": error_msg}
        
        # Executa a função de processamento
        updated_job = execute_comparison(job)
        
        logger.info(f"[JOB:{operation_id}] Job processado com status final: {updated_job.get_status()}")
        return {
            "success": True, 
            "job_id": operation_id,
            "status": str(updated_job.get_status())
        }
        
    except Operation.DoesNotExist:
        error_msg = f"Job não encontrado no banco: {operation_id}"
        logger.error(f"[JOB:{operation_id}] {error_msg}")
        return {"success": False, "error": error_msg}
            
    except Exception as e:
        logger.exception(f"[JOB:{operation_id}] Erro crítico no processamento: {str(e)}")
        
        # Tentar atualizar o status do job para falha
        try:
            operation = Operation.objects.get(operation_id=operation_id)
            job = operation.to_operation_data()
            job.update_status(EntityStatus.FAILED, f"Erro no processamento: {str(e)}")
            Operation.from_operation_data(job)
        except Exception:
            logger.exception(f"[JOB:{operation_id}] Erro ao atualizar status do job após falha")
        
        # Tentar retry da tarefa Celery
        try:
            self.retry(exc=e)
        except Exception as retry_error:
            logger.error(f"[JOB:{operation_id}] Erro ao agendar retry: {str(retry_error)}")
            
        return {"success": False, "error": str(e)}