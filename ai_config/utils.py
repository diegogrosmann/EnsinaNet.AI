from .models import (
    AIClientConfiguration, 
)
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS
import logging

logger = logging.getLogger(__name__)

def perform_training(user, token):
    results = {}
    for ai_client_config in AIClientConfiguration.objects.filter(token=token, enabled=True):
        ai_client_name = ai_client_config.ai_client.api_client_class
        ai_client_cls = next((cls for cls in AVAILABLE_AI_CLIENTS if cls.name == ai_client_name), None)
        
        if not ai_client_cls:
            results[ai_client_name] = "Erro: Classe de IA não encontrada."
            continue

        # Verificar se a IA pode ser treinada
        if not ai_client_cls.can_train:
            results[ai_client_name] = "Erro: Esta IA não suporta treinamento."
            continue

        # Obter o arquivo de treinamento do TokenAIConfiguration
        token_ai_config = token.ai_configuration
        training_file = token_ai_config.training_file
        if not training_file:
            results[ai_client_name] = "Erro: Arquivo de treinamento não selecionado para o token."
            continue

        try:
            result = perform_training_for_single_ai(user, token, ai_client_config, training_file)
            results[ai_client_name] = result[1]
        except Exception as e:
            results[ai_client_name] = f"Erro: {str(e)}"
    
    return results

def perform_training_for_single_ai(user, token, ai_client_config, training_file):
    ai_client_name = ai_client_config.ai_client.api_client_class
    ai_client_cls = next(
        (cls for cls in AVAILABLE_AI_CLIENTS if cls.name == ai_client_name), None
    )

    if not ai_client_cls:
        return ai_client_name, "Erro: Classe de IA não encontrada."

    # Verificar se a IA pode ser treinada
    if not ai_client_cls.can_train:
        return ai_client_name, "Erro: Esta IA não suporta treinamento."

    try:
        parametersAITraining = ai_client_config.training.training_parameters

        client = ai_client_cls(
            api_key=ai_client_config.ai_client.api_key,
            model_name=ai_client_config.model_name,
            configurations=ai_client_config.configurations,
        )
        # Usar o arquivo de treinamento
        trained_model_name = client.train(training_file.file, parametersAITraining)
        ai_client_config.training.trained_model_name = trained_model_name
        ai_client_config.training.save()

        logger.info(
            f"IA {ai_client_name} treinada com sucesso para token {token.name}. Modelo: {trained_model_name}"
        )
        return ai_client_name, f"Modelo treinado: {trained_model_name}"
    except Exception as e:
        logger.error(f"Erro ao treinar {ai_client_name} para token {token.name}: {e}")
        return ai_client_name, f"Erro: {str(e)}"