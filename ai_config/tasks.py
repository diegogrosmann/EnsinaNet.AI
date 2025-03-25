"""Tasks Celery para processamento assíncrono de treinamentos de IA.

Este módulo contém as tarefas agendadas para atualização de status de treinamentos.
"""

import logging
from celery import shared_task
from django.db import transaction
from core.types.training import TrainingStatus
from core.exceptions import TrainingError, AIConfigError, ApplicationError

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
    trainings = AITraining.objects.filter(status=TrainingStatus.IN_PROGRESS.value)
    processed_configs = set()
    
    for training in trainings:
        config_id = training.ai_config_id
        if config_id in processed_configs:
            continue  # Já processado para esta configuração
        try:
            client = training.ai_config.ai_client.create_api_client_instance()
            response = client.get_training_status(training.job_id)
            training.status = TrainingStatus.COMPLETED.value
            training.model_name = response.model_name
            training.error = None
            training.save()
            success_count += 1
        except (AIConfigError, TrainingError) as e:
            training.error = str(e)
            training.save()
            failure_count += 1
        except Exception as e:
            training.error = "Erro interno: " + str(e)
            training.save()
            failure_count += 1
        processed_configs.add(config_id)
    
    total = trainings.count()
    return {"success_count": success_count, "failure_count": failure_count, "total": total}