import logging

from django.http import JsonResponse

from rest_framework.decorators import api_view
from rest_framework import status

from concurrent.futures import ThreadPoolExecutor, as_completed

from api.exceptions import APIClientError, FileProcessingError
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS

from accounts.models import UserToken, TokenConfiguration

logger = logging.getLogger(__name__)


def process_client(AIClientClass, method_name, data, user_token):
    ai_client_name = AIClientClass.name
    try:
        token_config = user_token.configurations.get(api_client_class=ai_client_name)
        configurations = token_config.configurations
    except TokenConfiguration.DoesNotExist:
        configurations = {}

    try:
        ai_client = AIClientClass(configurations=configurations)
        compare_method = getattr(ai_client, method_name, None)
        if not compare_method:
            logger.warning(f"O método '{method_name}' não está implementado para {ai_client_name}.")
            return ai_client_name, {"error": f"Método '{method_name}' não implementado."}

        result = compare_method(data)
        logger.info(f"Comparação de '{method_name}' com {ai_client_name} realizada com sucesso.")
        return ai_client_name, result
    except APIClientError as e:
        logger.error(f"Erro na comparação de '{method_name}' com {ai_client_name}: {e}")
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

    comparison_types = {
        'complete_comparison': {
            'required_keys': {'student', 'instruction', 'instructor'},
            'method_name': 'compare_complete'
        },
        'lab': {
            'required_keys': {'student', 'instructor'},
            'method_name': 'compare_labs'
        },
        'instruction': {
            'required_keys': {'instruction', 'student'},
            'method_name': 'compare_instruction'
        },
        'instruction_only': {
            'required_keys': {'instruction'},
            'method_name': 'compare_instruction'
        },
    }

    detected_type = None
    for comp_type, config in comparison_types.items():
        if config['required_keys'].issubset(data.keys()):
            if detected_type is None or len(config['required_keys']) > len(comparison_types[detected_type]['required_keys']):
                detected_type = comp_type

    if not detected_type:
        logger.error("Nenhum tipo de comparação detectado. Verifique as chaves do JSON.")
        response_data["error"] = "Tipo de comparação não detectado ou chaves ausentes."
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    comparison_type = detected_type
    logger.info(f"Tipo de comparação detectado: {comparison_type}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_client, AIClientClass, comparison_types[comparison_type]['method_name'], data, user_token) for AIClientClass in AVAILABLE_AI_CLIENTS]

        for future in as_completed(futures):
            client_name, result = future.result()
            response_ias[client_name] = result

    response_data['IAs'] = response_ias
    response_data['comparison_type'] = comparison_type

    logger.info("Operação compare finalizada.")
    return JsonResponse(response_data, status=status.HTTP_200_OK)
