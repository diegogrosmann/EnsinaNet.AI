"""Tasks Celery para processamento assíncrono de treinamentos de IA.

Este módulo contém as tarefas agendadas para atualização de status de treinamentos.
"""

import logging
from celery import shared_task
from django.db import transaction
from .models import AITraining


# Alterar o logger para usar o namespace específico de tasks
logger = logging.getLogger('ai_config.tasks')

@shared_task
def update_training_status():
    """Atualiza o status dos treinamentos em andamento.
    
    Consulta todos os treinamentos marcados como 'in_progress' e atualiza
    seus status consultando as APIs respectivas.
    """
    logger.info("Iniciando atualização de status dos treinamentos")
    
    try:
        trainings = AITraining.objects.filter(
            status='in_progress'
        ).select_related('ai_config', 'ai_config__ai_client')
        
        logger.debug(f"Encontrados {trainings.count()} treinamentos em andamento")
        
        for training in trainings:
            try:
                with transaction.atomic():
                    client = training.ai_config.create_api_client_instance()
                    if not client.can_train:
                        logger.warning(f"IA '{training.ai_config.name}' não suporta treinamento")
                        continue
                        
                    status = client.get_training_status(training.job_id)
                    
                    # Atualiza o registro no banco com o progresso
                    training.status = status.status.value
                    training.progress = status.progress or 0
                    if status.model_name:
                        training.model_name = status.model_name
                    training.error = status.error
                    training.save()
                    
                    logger.info(
                        f"Status atualizado para treinamento {training.job_id}: "
                        f"status={status.status.value}, progresso={status.progress:.1%}"
                    )
                    
            except Exception as e:
                logger.error(f"Erro ao atualizar treinamento {training.job_id}: {e}")
                training.error = str(e)
                training.save()
                
        logger.info("Atualização de status dos treinamentos concluída")
                
    except Exception as e:
        logger.exception(f"Erro crítico durante atualização de status: {e}")
        raise
