# api/views.py

from rest_framework.decorators import api_view
from rest_framework import status
from django.http import JsonResponse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from accounts.models import UserToken
from api.exceptions import APIClientError, FileProcessingError
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS

@api_view(['POST'])
def compare(request):
    logger = logging.getLogger(__name__)
    logger.info("Iniciando a operação compare.")
    response_data = {}
    response_ias = {}

    # Verificar se o token está presente nos headers
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    try:
        user_token = UserToken.objects.get(key=token_key)
        user = user_token.user
    except UserToken.DoesNotExist:
        logger.error("Token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)

    # Parsing do JSON recebido
    try:
        data = request.data
        logger.debug("Dados recebidos!")
    except Exception as e:
        logger.error(f"Erro ao processar a requisição: {e}")
        response_data["error"] = "Erro interno ao processar a requisição."
        return JsonResponse(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Definição das configurações para cada tipo de comparação
    comparison_types = {
        'lab': {
            'required_keys': ['instructor_config', 'instructor_network', 'student_config', 'student_network'],
            'method_name': 'compare_labs'
        },
        'instruction': {
            'required_keys': ['instruction', 'student_config', 'student_network'],
            'method_name': 'compare_instruction'
        },
        'complete_comparison': {
            'required_keys': ['instruction', 'instructor_config', 'instructor_network', 'student_config', 'student_network'],
            'method_name': 'compare_complete'
        },
        # Você pode adicionar novos tipos de comparação aqui
    }

    # Identificação do tipo de comparação com base nas chaves presentes
    detected_types = []
    for comp_type, config in comparison_types.items():
        if all(key in data for key in config['required_keys']):
            detected_types.append(comp_type)

    if not detected_types:
        logger.error("Nenhum tipo de comparação detectado. Verifique as chaves do JSON.")
        response_data["error"] = "Tipo de comparação não detectado ou chaves ausentes."
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    if len(detected_types) > 1:
        logger.error("Múltiplos tipos de comparação detectados. Por favor, envie apenas um tipo por requisição.")
        response_data["error"] = "Múltiplos tipos de comparação detectados. Envie apenas um tipo por requisição."
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    comparison_type = detected_types[0]
    config = comparison_types[comparison_type]
    logger.info(f"Tipo de comparação detectado: {comparison_type}")

    # Função auxiliar para processar cada cliente de IA
    def process_client(AIClientClass, method_name, data):
        ai_client_name = AIClientClass.name
        try:
            with AIClientClass() as ai_client:
                compare_method = getattr(ai_client, method_name, None)
                if not compare_method:
                    logger.warning(f"O método '{method_name}' não está implementado para {ai_client_name}.")
                    return ai_client_name, {"error": f"Método '{method_name}' não implementado."}

                result = compare_method(data)
                logger.info(f"Comparação de '{comparison_type}' com {ai_client_name} realizada com sucesso.")
                return ai_client_name, result
        except APIClientError as e:
            logger.error(f"Erro na comparação de '{comparison_type}' com {ai_client_name}: {e}")
            return ai_client_name, {"error": str(e)}
        except FileProcessingError as e:
            logger.error(f"Erro no processamento de arquivos para {ai_client_name}: {e}")
            return ai_client_name, {"error": str(e)}
        except Exception as e:
            logger.error(f"Erro inesperado ao utilizar {ai_client_name}: {e}")
            return ai_client_name, {"error": "Erro interno ao processar a requisição com " + ai_client_name}

    # Utilizar ThreadPoolExecutor para executar as comparações em paralelo
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submeter todas as tarefas ao executor
        futures = [executor.submit(process_client, AIClientClass, config['method_name'], data) for AIClientClass in AVAILABLE_AI_CLIENTS]
        
        # Coletar os resultados conforme são completados
        for future in as_completed(futures):
            client_name, result = future.result()
            response_ias[client_name] = result

    # Estrutura da resposta padronizada com a chave 'IAs'
    response_data['IAs'] = response_ias

    # Adicionar o tipo de comparação na resposta para contexto adicional
    response_data['comparison_type'] = comparison_type

    logger.info("Operação compare finalizada.")
    return JsonResponse(response_data, status=status.HTTP_200_OK)
