import logging
import json

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework import status

from concurrent.futures import ThreadPoolExecutor, as_completed

from api.exceptions import APIClientError, FileProcessingError, MissingAPIKeyError
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS, extract_text

from accounts.models import UserToken
from ai_config.models import AIClientGlobalConfiguration, TrainingCapture, AITrainingFile

logger = logging.getLogger(__name__)

def process_client(AIClientClass, processed_data, user_token):
    ai_client_name = AIClientClass.name
    try:
        # Obter o AIClient
        ai_client = AIClientGlobalConfiguration.objects.get(api_client_class=ai_client_name)
        ai_client_config = user_token.configurations.get(ai_client=ai_client)
        if not ai_client_config.enabled:
            logger.info(f"{ai_client_name} está desabilitado para este token.")
            return ai_client_name, {"message": "Esta IA está desabilitada."}

        model_name = ai_client_config.model_name or AIClientClass.default_model_name
        configurations = ai_client_config.configurations.copy()

        token_ai_config = user_token.ai_configuration
        base_instruction = token_ai_config.base_instruction or ""
        prompt = token_ai_config.prompt or ""
        responses = token_ai_config.responses or ""

        ai_client_training = getattr(ai_client_config, 'training', None)
        if ai_client_training and ai_client_training.trained_model_name:
            model_name = ai_client_training.trained_model_name

        # Inicializar o cliente de IA
        ai_client_instance = AIClientClass(
            api_key=ai_client.api_key,
            model_name=model_name,
            configurations=configurations,
            base_instruction=base_instruction,
            prompt=prompt,
            responses=responses
        )

        # Realizar a comparação
        comparison_result, system_message, user_message = ai_client_instance.compare(processed_data)

        # Verificar se a captura está ativa
        try:
            capture = TrainingCapture.objects.get(token=user_token, ai_client=ai_client)
            temp_file = capture.temp_file
            if capture.is_active and temp_file:
                # Ler os dados existentes
                try:
                    with temp_file.open('r') as f:
                        training_data = json.load(f)
                except json.JSONDecodeError:
                    training_data = []

                # Adicionar o novo exemplo
                new_example = {
                    'system_message': system_message,
                    'user_message': user_message,
                    'response': comparison_result
                }
                training_data.append(new_example)

                # Salvar de volta no arquivo temporário
                with temp_file.open('w') as f:
                    json.dump(training_data, f, ensure_ascii=False, indent=4)

                logger.info(f"Novo exemplo adicionado ao arquivo temporário para {ai_client_name} do Token {user_token.name}.")
        except TrainingCapture.DoesNotExist:
            pass  # Captura não está ativa

        return ai_client_name, {"response": comparison_result}

    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_client_name}: {e}")
        return ai_client_name, {"error": "Chave de API não configurada para esta IA."}
    except APIClientError as e:
        logger.error(f"Erro na comparação com {ai_client_name}: {e}")
        return ai_client_name, {"error": str(e)}
    except FileProcessingError as e:
        logger.error(f"Erro no processamento de arquivos para {ai_client_name}: {e}")
        return ai_client_name, {"error": str(e)}
    except Exception as e:
        logger.error(f"Erro inesperado ao utilizar {ai_client_name}: {e}")
        return ai_client_name, {"error": "Erro interno ao processar a requisição com " + ai_client_name}

@api_view(['POST'])
def compare(request):
    logger.info("Iniciando a operação compare.")
    response_data = {}
    response_ias = {}

    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    try:
        user_token = UserToken.objects.get(key=token_key)
    except UserToken.DoesNotExist:
        logger.error("Token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        data = request.data
        logger.debug("Dados recebidos!")
    except Exception as e:
        logger.error(f"Erro ao processar a requisição: {e}")
        response_data["error"] = "Erro interno ao processar a requisição."
        return JsonResponse(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def process_file_content(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, dict):
                    if value.get("type") == "file":
                        processed_value = extract_text(value)
                        obj[key] = processed_value
                    else:
                        process_file_content(value)
                elif isinstance(value, list):
                    process_file_content(value)
        elif isinstance(obj, list):
            for item in obj:
                process_file_content(item)

    process_file_content(data)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                process_client, 
                AIClientClass, 
                data, 
                user_token
            ) 
            for AIClientClass in AVAILABLE_AI_CLIENTS
        ]

        for future in as_completed(futures):
            client_name, result = future.result()
            response_ias[client_name] = result

    response_data['IAs'] = response_ias

    logger.info("Operação compare finalizada.")

    logger.debug(f"Dados Processados: {data}")
    logger.debug(f"Resposta: {response_data}")
    return JsonResponse(response_data, status=status.HTTP_200_OK)
