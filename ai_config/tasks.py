"""Tasks Celery para processamento assíncrono de treinamentos de IA.

Este módulo contém as tarefas agendadas para atualização de status de treinamentos.
"""

import logging
from celery import shared_task
from ai_config.exceptions import AIConfigException, TrainingException
from core.types import EntityStatus

from .models import AITraining

# Alterar o logger para usar o namespace específico de tasks
logger = logging.getLogger('ai_config.tasks')

@shared_task
def update_training_status():
    """Atualiza o status dos treinamentos em andamento.
    
    Consulta todos os treinamentos marcados como 'in_progress' e atualiza
    seus status consultando as APIs respectivas.
    
    Returns:
        dict: Resumo da execução, contendo contagens de sucesso e falhas.
    """
    success_count = 0
    failure_count = 0
    trainings = AITraining.objects.filter(status=EntityStatus.IN_PROGRESS.value)
    
    for training in trainings:
        try:
            # Utiliza o novo método update_training_status
            if training.update_training_status():
                success_count += 1
                logger.info(f"Status do treinamento {training.job_id} atualizado com sucesso")
            else:
                failure_count += 1
                logger.warning(f"Falha ao atualizar status do treinamento {training.job_id}")
        except Exception as e:
            logger.error(f"Erro ao atualizar treinamento {training.job_id}: {e}", exc_info=True)
            failure_count += 1
    
    total = trainings.count()
    logger.info(f"Atualização de status concluída: {success_count} sucessos, {failure_count} falhas, total de {total}")
    return {"success_count": success_count, "failure_count": failure_count, "total": total}