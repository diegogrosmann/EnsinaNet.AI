from threading import Thread
from .models import AIClientConfiguration, AITraining
import logging


logger = logging.getLogger(__name__)

def perform_training(selected_ias, training_file):
    """Inicia o treinamento para as IAs selecionadas usando threads."""
    results = []
    threads = []
    
    def train_single_ia(ai_id):
        try:
            config = AIClientConfiguration.objects.get(id=ai_id)
            
            try:
                client = config.create_api_client_instance()
            except ValueError as e:
                logger.error(f"Cliente inválido para IA {ai_id}: {e}")
                results.append({
                    'ai_name': f"IA {ai_id}",
                    'error': str(e),
                    'status': 'failed'
                })
                return
            
            if not client.can_train:
                results.append({
                    'ai_name': config.name,
                    'error': "Esta IA não suporta treinamento",
                    'status': 'failed'
                })
                return
                
            result = client.train(training_file.file.path)
            
            training = AITraining.objects.create(
                ai_config=config,
                file=training_file,
                job_id=result.job_id,
                status=result.status.value
            )
            
            results.append({
                'ai_name': config.name,
                'job_id': training.job_id,
                'status': 'initiated'
            })
            
        except Exception as e:
            logger.error(f"Erro ao iniciar treinamento para IA {ai_id}: {e}", exc_info=True)
            results.append({
                'ai_name': config.name if 'config' in locals() else f"IA {ai_id}",
                'error': str(e),
                'status': 'failed'
            })
    
    # Cria uma thread para cada IA selecionada
    for ai_id in selected_ias:
        thread = Thread(target=train_single_ia, args=(ai_id,))
        thread.start()
        threads.append(thread)
    
    # Aguarda todas as threads terminarem
    for thread in threads:
        thread.join()
    
    return results

def perform_training_for_single_ai(user, token, ai_client_config, training_file):
    """Realiza o treinamento para uma única IA.

    Args:
        user: Usuário que solicitou o treinamento.
        token: Token associado à configuração.
        ai_client_config: Configuração específica do cliente de IA.
        training_file: Arquivo de treinamento associado.

    Returns:
        tuple: Par contendo o nome da IA e o resultado do treinamento.
    """
    try:
        client = ai_client_config.create_api_client_instance()
    except ValueError as e:
        return ai_client_config.name, f"Erro: {str(e)}"

    if not client.can_train:
        return ai_client_config.name, "Erro: Esta IA não suporta treinamento."

    try:
        parametersAITraining = ai_client_config.training.training_parameters
        
        # Usar o arquivo de treinamento
        trained_model_name = client.train(training_file.file, parametersAITraining)
        ai_client_config.training.trained_model_name = trained_model_name
        ai_client_config.training.save()

        logger.info(
            f"IA {client.name} treinada com sucesso para token {token.name}. Modelo: {trained_model_name}"
        )
        return client.name, f"Modelo treinado: {trained_model_name}"
    except Exception as e:
        logger.error(f"Erro ao treinar {client.name} para token {token.name}: {e}")
        return client.name, f"Erro: {str(e)}"