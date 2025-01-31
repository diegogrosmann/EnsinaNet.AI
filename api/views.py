import logging
import json
import time

from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from rest_framework.decorators import api_view
from rest_framework import status
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.constants import AIClientConfig
from api.exceptions import APICommunicationError, MissingAPIKeyError
from api.utils.clientsIA import AI_CLIENT_MAPPING, extract_text

from accounts.models import UserToken
from ai_config.models import TrainingCapture, AIClientConfiguration

logger = logging.getLogger(__name__)

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

def process_client(ai_config, processed_data, user_token):
    """Processa a requisição para uma configuração específica de cliente IA."""
    
    try:
        start_time = time.perf_counter()  # Início da medição
        
        # Verificar se a configuração está habilitada
        if not ai_config.enabled:
            logger.info(f"{ai_config.name} está desabilitada para este token.")
            return ai_config, {"message": "Esta IA está desabilitada."}

        # Preparar configurações do cliente
        config = AIClientConfig(
            api_key=ai_config.ai_client.api_key,
            api_url=ai_config.ai_client.api_url,
            model_name=getattr(ai_config, 'trained_model_name', None) or ai_config.model_name,
            configurations=ai_config.configurations.copy(),
            base_instruction=user_token.ai_configuration.base_instruction or "",
            prompt=user_token.ai_configuration.prompt or "",
            responses=user_token.ai_configuration.responses or "",
            enabled=ai_config.enabled
        )

        # Adicionar arquivo de treinamento aos dados processados, se existir
        training_file = user_token.ai_configuration.training_file.file if user_token.ai_configuration.training_file else None
        if training_file:
            processed_data['training_file'] = training_file

        # Inicializar e executar o cliente
        client_class = AI_CLIENT_MAPPING.get(ai_config.ai_client.api_client_class)
        if not client_class:
            raise APICommunicationError(f"Cliente de IA '{ai_config.ai_client.api_client_class}' não está mapeado.")
        
        ai_client_instance = client_class(config)
        comparison_result, system_message, user_message = ai_client_instance.compare(processed_data)

        # Gerenciar captura de treinamento
        handle_training_capture(user_token, ai_config.ai_client, system_message, user_message, comparison_result)

        processing_time = round(time.perf_counter() - start_time, 2)
        result = ai_config, {
            "response": comparison_result,
            "model_name": config.model_name,
            "configurations": config.configurations,
            "processing_time": processing_time
        }
        return result

    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_config.ai_client.api_client_class}: {e}")
        return ai_config, {"error": "Chave de API não configurada para esta IA."}
    except Exception as e:
        logger.error(f"Erro ao processar {ai_config.ai_client.api_client_class}: {e}")
        return ai_config, {"error": str(e)}
    
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
    """Processa a requisição para todos os clientes IA configurados para o usuário."""
    response_ias = {}
    # Filtra apenas as configurações de IA vinculadas ao user_token
    user_ai_configs = AIClientConfiguration.objects.filter(token=user_token, enabled=True)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for ai_config in user_ai_configs:
            futures.append(
                executor.submit(process_client, ai_config, processed_data, user_token)
            )

        for future in as_completed(futures):
            ai_config, result = future.result()
            response_ias[ai_config.name] = result  # Usa o nome personalizado para identificar

    return response_ias

