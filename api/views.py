import logging
import json

from django.http import JsonResponse

from rest_framework.decorators import api_view
from rest_framework import status

from concurrent.futures import ThreadPoolExecutor, as_completed

from api.exceptions import APIClientError, FileProcessingError, MissingAPIKeyError
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS, extract_text

from accounts.models import UserToken, TokenConfiguration, AIClientConfiguration, GlobalConfiguration

logger = logging.getLogger(__name__)

def process_client(AIClientClass, processed_data, user_token):
    ai_client_name = AIClientClass.name
    try:
        # Obter a configuração padrão da API
        try:
            default_config = AIClientConfiguration.objects.get(api_client_class=ai_client_name)
            api_key = default_config.api_key
            model_name = default_config.model_name
            configurations = default_config.configurations.copy()
        except AIClientConfiguration.DoesNotExist:
            logger.error(f"Configuração padrão para {ai_client_name} não encontrada.")
            raise MissingAPIKeyError(f"Configuração padrão para {ai_client_name} não encontrada.")

        # Obter configurações globais de Prompt
        try:
            global_config = GlobalConfiguration.objects.first()
            base_instruction_global = global_config.base_instruction if global_config else ""
            prompt_global = global_config.prompt if global_config else ""
            responses_global = global_config.responses if global_config else ""
        except GlobalConfiguration.DoesNotExist:
            base_instruction_global = ""
            prompt_global = ""
            responses_global = ""

        # Obter configurações específicas da API, se houver
        try:
            token_config = user_token.configurations.get(api_client_class=ai_client_name)
            if not token_config.enabled:
                logger.info(f"{ai_client_name} está desabilitado para este token.")
                return ai_client_name, {"message": "Esta IA está desabilitada."}
            
            # Sobrescrever model_name e configurations se fornecidos pelo usuário
            if token_config.model_name:
                model_name = token_config.model_name
            if token_config.configurations:
                configurations.update(token_config.configurations)
        except TokenConfiguration.DoesNotExist:
            logger.info(f"{ai_client_name} não tem configuração específica para este token. Usando configurações globais.")
        
        # Obter as configurações especificas do Prompt, se houver
        base_instruction = user_token.base_instruction if user_token.base_instruction else base_instruction_global
        prompt = user_token.prompt if user_token.prompt else prompt_global
        responses = user_token.responses if user_token.responses else responses_global

        # Inicializar o cliente de IA com as configurações apropriadas
        ai_client = AIClientClass(
            api_key=api_key, 
            model_name=model_name, 
            configurations=configurations, 
            base_instruction=base_instruction, 
            prompt=prompt, 
            responses=responses
        )

        # Chamar o método compare com processed_data
        comparison_result = ai_client.compare(processed_data)

        logger.info(f"Comparação com {ai_client_name} realizada com sucesso.")
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
                    # Verifica se o dicionário possui 'type': 'file'
                    if value.get("type") == "file":
                        # Processa o conteúdo do arquivo
                        processed_value = extract_text(value)
                        # Insere o conteúdo processado diretamente na chave atual
                        obj[key] = processed_value
                    else:
                        # Chama a função recursivamente para outros dicionários
                        process_file_content(value)
                elif isinstance(value, list):
                    # Chama a função recursivamente para cada item da lista
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
    return JsonResponse(response_data, status=status.HTTP_200_OK)
