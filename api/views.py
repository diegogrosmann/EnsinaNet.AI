import logging
import json

from django.http import JsonResponse

from rest_framework.decorators import api_view
from rest_framework import status

from concurrent.futures import ThreadPoolExecutor, as_completed

from api.exceptions import APIClientError, FileProcessingError, MissingAPIKeyError
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS, extract_text

from accounts.models import UserToken, TokenConfiguration, AIClientConfiguration

logger = logging.getLogger(__name__)

def process_client(AIClientClass, processed_data, user_token):
    ai_client_name = AIClientClass.name
    try:
        # Obter a configuração padrão do ADM
        try:
            default_config = AIClientConfiguration.objects.get(api_client_class=ai_client_name)
            api_key = default_config.api_key
            model_name = default_config.model_name
            configurations = default_config.configurations.copy()
        except AIClientConfiguration.DoesNotExist:
            logger.error(f"Configuração padrão para {ai_client_name} não encontrada.")
            raise MissingAPIKeyError(f"Configuração padrão para {ai_client_name} não encontrada.")

        # Obter configurações específicas do usuário, se houver
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
            logger.info(f"{ai_client_name} não tem configuração específica para este token.")
            # Manter as configurações padrão
        except Exception as e:
            logger.error(f"Erro ao obter configurações para {ai_client_name}: {e}")
            # Manter as configurações padrão

       
        # Inicializar o cliente de IA
        ai_client = AIClientClass(api_key=api_key, model_name=model_name, configurations=configurations)

        # Chamar o método compare com comparison_type e processed_data
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

    processed_data = {}

    instructor = data.get('instructor')
    instruction = instructor.get('instruction')
    lab = instructor.get('lab')

    instructor_date = {}

    if instruction:
        instructor_date['instruction'] = extract_text(instruction)
        
    if lab:
        lab_date = {}
        lab_date['config'] = json.dumps(lab['config'], indent=4)
        lab_date['network'] = json.dumps(lab['network'], indent=4)
        instructor_date['lab'] = lab_date

    processed_data['instructor'] = instructor_date

    student = data.get('student')
    answers = student.get('answers')
    lab = student.get('lab')

    student_data = {}
    if answers:
        student_data['answers'] = extract_text(answers)
    
    if lab:
        lab_date = {}
        lab_date['config'] = json.dumps(lab['config'], indent=4)
        lab_date['network'] = json.dumps(lab['network'], indent=4)
        student_data['lab'] = lab_date

    processed_data['student'] = student_data

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                process_client, 
                AIClientClass, 
                processed_data, 
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
