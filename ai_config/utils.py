from .models import AIClientConfiguration
from api.utils.clientsIA import AI_CLIENT_MAPPING
import concurrent.futures
import logging

logger = logging.getLogger(__name__)

def perform_training(user, token, selected_ias=None):
    results = {}

    # Obter as AIClientConfigurations para o token, filtrando pelas IAs selecionadas
    if selected_ias:
        ai_client_configs = AIClientConfiguration.objects.filter(
            token=token,
            enabled=True,
            ai_client__api_client_class__in=selected_ias
        )
    else:
        ai_client_configs = AIClientConfiguration.objects.filter(
            token=token,
            enabled=True
        )

    def train_ai(ai_client_config):
        ai_client_name = ai_client_config.ai_client.api_client_class
        ai_client_cls = CLIENT_CLASSES.get(ai_client_name)

        if not ai_client_cls:
            return ai_client_name, f"Erro: Cliente de IA '{ai_client_name}' não encontrado no mapeamento."

        # Verificar se a IA pode ser treinada
        if not ai_client_cls.can_train:
            return ai_client_name, "Erro: Esta IA não suporta treinamento."

        # Obter o arquivo de treinamento do TokenAIConfiguration
        token_ai_config = token.ai_configuration
        training_file = token_ai_config.training_file
        if not training_file:
            return ai_client_name, "Erro: Arquivo de treinamento não selecionado para o token."

        try:
            result = perform_training_for_single_ai(user, token, ai_client_config, training_file)
            return ai_client_name, result[1]
        except Exception as e:
            logger.error(f"Erro ao treinar {ai_client_name} para token {token.name}: {e}")
            return ai_client_name, f"Erro: {str(e)}"

    # Usar ThreadPoolExecutor para treinar as IAs em paralelo
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(train_ai, ai_client_config): ai_client_config.ai_client.api_client_class
            for ai_client_config in ai_client_configs
        }

        for future in concurrent.futures.as_completed(futures):
            ai_client_name = futures[future]
            try:
                ai_client_name_result, result = future.result()
                results[ai_client_name_result] = result
            except Exception as e:
                logger.error(f"Erro inesperado ao treinar {ai_client_name} para token {token.name}: {e}")
                results[ai_client_name] = f"Erro: {str(e)}"

    return results

def perform_training_for_single_ai(user, token, ai_client_config, training_file):
    ai_client_name = ai_client_config.ai_client.api_client_class
    ai_client_cls = CLIENT_CLASSES.get(ai_client_name)

    if not ai_client_cls:
        return ai_client_name, f"Erro: Cliente de IA '{ai_client_name}' não encontrado no mapeamento."

    # Verificar se a IA pode ser treinada
    if not ai_client_cls.can_train:
        return ai_client_name, "Erro: Esta IA não suporta treinamento."

    try:
        parametersAITraining = ai_client_config.training.training_parameters

        client = ai_client_cls({
            'api_key': ai_client_config.ai_client.api_key,
            'model_name': ai_client_config.model_name,
            'configurations': ai_client_config.configurations,
            'base_instruction': '',
            'prompt': '',
            'responses': ''
        })
        
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