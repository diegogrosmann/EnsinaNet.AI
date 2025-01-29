import logging
import json
import time  # Importar o módulo time
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework import status
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.exceptions import MissingAPIKeyError
from api.utils.clientsIA import AI_CLIENT_MAPPING, extract_text
from api.constants import AIClientType

from accounts.models import UserToken
from ai_config.models import AIClientGlobalConfiguration, TrainingCapture

logger = logging.getLogger(__name__)

def process_client(ai_type, processed_data, user_token):
    """Processa a requisição para um tipo específico de cliente IA."""
    
    try:
        start_time = time.perf_counter()  # Início da medição
        # Obter o AIClient
        ai_client = AIClientGlobalConfiguration.objects.get(api_client_class=ai_type.value)
        ai_client_config = user_token.configurations.get(ai_client=ai_client)
        
        if not ai_client_config.enabled:
            logger.info(f"{ai_type.value} está desabilitado para este token.")
            return ai_type.value, {"message": "Esta IA está desabilitada."}

        # Preparar configurações do cliente
        config = {
            'api_key': ai_client.api_key,
            'model_name': ai_client_config.model_name,
            'configurations': ai_client_config.configurations.copy(),
            'base_instruction': user_token.ai_configuration.base_instruction or "",
            'prompt': user_token.ai_configuration.prompt or "",
            'responses': user_token.ai_configuration.responses or ""
        }

        # Verificar modelo treinado
        ai_client_training = getattr(ai_client_config, 'training', None)
        if ai_client_training and ai_client_training.trained_model_name:
            config['model_name'] = ai_client_training.trained_model_name

        # Adicionar arquivo de treinamento aos dados processados
        training_file = user_token.ai_configuration.training_file.file if user_token.ai_configuration.training_file else None
        processed_data['training_file'] = training_file

        # Inicializar e executar o cliente
        client_class = AI_CLIENT_MAPPING[ai_type]
        ai_client_instance = client_class(config)
        comparison_result, system_message, user_message = ai_client_instance.compare(processed_data)

        # Gerenciar captura de treinamento
        handle_training_capture(user_token, ai_client, system_message, user_message, comparison_result)

        result = ai_type.value, {"response": comparison_result, "processing_time": round(time.perf_counter() - start_time, 2)}
        return result

    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_type.value}: {e}")
        return ai_type.value, {"error": "Chave de API não configurada para esta IA."}
    except Exception as e:
        logger.error(f"Erro ao processar {ai_type.value}: {e}")
        return ai_type.value, {"error": str(e)}

def handle_training_capture(user_token, ai_client, system_message, user_message, comparison_result):
    """Gerencia a captura de dados de treinamento."""
    try:
        capture = TrainingCapture.objects.get(token=user_token, ai_client=ai_client)
        if capture.is_active and capture.temp_file:
            try:
                with capture.temp_file.open('r') as f:
                    training_data = json.load(f)
            except json.JSONDecodeError:
                training_data = []

            training_data.append({
                'system_message': system_message,
                'user_message': user_message,
                'response': comparison_result
            })

            with capture.temp_file.open('w') as f:
                json.dump(training_data, f, ensure_ascii=False, indent=4)

            logger.info(f"Exemplo capturado para treinamento: {ai_client.api_client_class}")
    except TrainingCapture.DoesNotExist:
        pass

@api_view(['POST'])
def compare(request):
    """View principal para comparação de textos usando múltiplos modelos de IA."""
    logger.info("Iniciando operação compare.")
    
    # Validar token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    try:
        user_token = UserToken.objects.get(key=token_key)
    except UserToken.DoesNotExist:
        logger.error("Token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        processed_data = process_request_data(request.data)
        response_ias = process_all_clients(processed_data, user_token)
        logger.info("Operação compare finalizada com sucesso.")
        return JsonResponse({'IAs': response_ias}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erro na operação compare: {e}")
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_request_data(data):
    """Processa e extrai texto de arquivos nos dados da requisição."""
    def process_file_content(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, dict) and value.get("type") == "file":
                    obj[key] = extract_text(value)
                else:
                    process_file_content(value)
        elif isinstance(obj, list):
            for item in obj:
                process_file_content(item)

    processed_data = data.copy()
    process_file_content(processed_data)
    return processed_data

def process_all_clients(processed_data, user_token):
    """Processa a requisição para todos os clientes IA disponíveis."""
    response_ias = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(process_client, ai_type, processed_data, user_token)
            for ai_type in AIClientType
        ]

        for future in as_completed(futures):
            client_name, result = future.result()
            response_ias[client_name] = result

    return response_ias
