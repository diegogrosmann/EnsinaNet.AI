from celery import shared_task
from .models import AITraining
#import debugpy

@shared_task
def update_training_status():

    #debugpy.listen(5678)
    #print("Aguardando conexão do debugger...")
    #debugpy.wait_for_client()

    """Atualiza o status de todos os treinamentos em andamento."""
    trainings = AITraining.objects.filter(status='in_progress').select_related('ai_config')
    
    for training in trainings:
        try:
            client = training.ai_config.create_api_client_instance()
            if not client.can_train:
                continue
                
            status = client.get_training_status(training.job_id)
            
            # Atualiza o registro no banco com o progresso
            training.status = status.status.value
            training.progress = status.progress or 0
            if status.model_name:
                training.model_name = status.model_name
            training.error = status.error
            training.save()
            
        except Exception as e:
            training.error = str(e)
            training.save()
