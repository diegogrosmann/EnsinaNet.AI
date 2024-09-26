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
        # Recuperar as configurações para este token e classe de cliente de API
        try:
            token_config = user_token.configurations.get(api_client_class=ai_client_name)
            configurations = token_config.configurations
        except TokenConfiguration.DoesNotExist:
            configurations = {}

        try:
            with AIClientClass(configurations=configurations) as ai_client:
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
        'complete_comparison': {
            'required_keys': {'instruction', 'instructor_config', 'instructor_network', 'student_config', 'student_network'},
            'method_name': 'compare_complete'
        },
        'lab': {
            'required_keys': {'instructor_config', 'instructor_network', 'student_config', 'student_network'},
            'method_name': 'compare_labs'
        },
        'instruction': {
            'required_keys': {'instruction', 'student_config', 'student_network'},
            'method_name': 'compare_instruction'
        },
        # Adicione novos tipos de comparação aqui
    }

    # Identificação do tipo de comparação com base nas chaves presentes
    detected_type = None
    for comp_type, config in comparison_types.items():
        if config['required_keys'].issubset(data.keys()):
            # Verifica se o conjunto de chaves é exatamente igual ao requerido
            if config['required_keys'] == set(data.keys()):
                detected_type = comp_type
                break
            # Alternativamente, se você quiser permitir chaves adicionais, mas evitar sobreposição:
            elif detected_type is None:
                detected_type = comp_type

    if not detected_type:
        logger.error("Nenhum tipo de comparação detectado. Verifique as chaves do JSON.")
        response_data["error"] = "Tipo de comparação não detectado ou chaves ausentes."
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    # Verifica se há múltiplos tipos detectados
    matched_types = []
    for comp_type, config in comparison_types.items():
        if config['required_keys'].issubset(data.keys()):
            matched_types.append(comp_type)
    
    # Priorizar tipos de comparação com mais chaves
    if len(matched_types) > 1:
        # Ordena os tipos por número de chaves descendente
        matched_types.sort(key=lambda x: len(comparison_types[x]['required_keys']), reverse=True)
        detected_type = matched_types[0]
        logger.warning("Múltiplos tipos de comparação detectados. Selecionando o mais específico.")

    comparison_type = detected_type
    logger.info(f"Tipo de comparação detectado: {comparison_type}")

    # Utilizar ThreadPoolExecutor para executar as comparações em paralelo
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submeter todas as tarefas ao executor
        futures = [executor.submit(process_client, AIClientClass, comparison_types[comparison_type]['method_name'], data, user_token) for AIClientClass in AVAILABLE_AI_CLIENTS]
        
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

