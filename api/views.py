import logging
import json
import time

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework import status
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.constants import AIClientConfig
from api.exceptions import APICommunicationError, MissingAPIKeyError
from api.utils.clientsIA import AI_CLIENT_MAPPING

from accounts.models import UserToken
from ai_config.models import TrainingCapture, AIClientConfiguration

from api.utils.doc_extractor import extract_text

logger = logging.getLogger(__name__)

@api_view(['POST'])
def compare(request):
    """
    View principal para comparação de textos usando múltiplos modelos de IA em
    processamento em lote.

    O JSON enviado deve conter:
      - "instructor": com a instrução e (opcionalmente) dados do laboratório do professor.
      - "students": uma lista de objetos, cada um contendo o "id" do aluno e, se desejado,
        sua própria resposta (campo renomeado para "student_response") e/ou configuração de laboratório.

    O arquivo do instrutor (por exemplo, instrução em base64) será processado apenas uma vez,
    e o resultado será mesclado com os dados de cada aluno.

    Retorna um dicionário com as respostas de cada aluno identificadas pelo seu "id".
    """
    logger.info("Iniciando operação compare em lote.")
    
    # Validação do token de autenticação
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    try:
        user_token = UserToken.objects.get(key=token_key)
    except UserToken.DoesNotExist:
        logger.error("Token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        data = request.data
        if "students" not in data:
            return JsonResponse({"error": "A solicitação deve conter a chave 'students' para processamento."},
                                status=status.HTTP_400_BAD_REQUEST)
        
        if "instructor" not in data:
            return JsonResponse({"error": "A solicitação deve conter a chave 'instructor' para processamento."},
                                status=status.HTTP_400_BAD_REQUEST)
        
        instructor_data = data["instructor"]
        students_data = data["students"]

        # Processa o conteúdo do instrutor apenas uma vez
        processed_instructor = process_request_data(instructor_data)
        
        batch_results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for index, student in enumerate(students_data):
                
                payload = {}
                # Cria um payload mesclando os dados processados do instrutor com os dados do aluno.
                payload['instructor'] = processed_instructor
                payload['student'] = students_data[student]
                
                # Processa apenas o conteúdo dos dados do aluno (se houver arquivos)
                processed_payload = process_request_data(payload)
                futures[executor.submit(process_all_clients, processed_payload, user_token)] = student

            for future in as_completed(futures):
                nindex = futures[future]
                try:
                    result = future.result()
                    batch_results[nindex] = result
                except Exception as e:
                    logger.error(f"Erro ao processar o aluno {nindex}: {e}")
                    batch_results[nindex] = {"error": str(e)}
        
        logger.info("Operação compare em lote finalizada com sucesso.")
        return JsonResponse({"students": batch_results}, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Erro na operação compare: {e}")
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_client(ai_config, processed_data, user_token):
    """
    Processa a requisição para uma configuração específica de cliente de IA.
    """
    try:
        start_time = time.perf_counter()
        
        if not ai_config.enabled:
            logger.info(f"{ai_config.name} está desabilitada para este token.")
            return ai_config, {"message": "Esta IA está desabilitada."}

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

        training_file = user_token.ai_configuration.training_file.file if user_token.ai_configuration.training_file else None
        if training_file:
            processed_data['training_file'] = training_file

        client_class = AI_CLIENT_MAPPING.get(ai_config.ai_client.api_client_class)
        if not client_class:
            raise APICommunicationError(f"Cliente de IA '{ai_config.ai_client.api_client_class}' não está mapeado.")
        
        ai_client_instance = client_class(config)
        comparison_result, system_message, user_message = ai_client_instance.compare(processed_data)

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
    """
    Gerencia a captura de dados de treinamento, adicionando exemplos ao arquivo temporário se houver captura ativa.
    """
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
    """
    Processa e extrai texto de arquivos nos dados fornecidos.
    Percorre recursivamente dicionários e listas e, quando encontra um objeto do tipo arquivo
    (com "type" == "file"), substitui-o pelo texto extraído usando extract_text.
    """
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

    processed = data.copy()
    process_file_content(processed)
    return processed

def process_all_clients(processed_data, user_token):
    """
    Processa a requisição para todos os clientes de IA vinculados ao token, utilizando paralelismo.
    Retorna um dicionário com os resultados, usando o nome da configuração como chave.
    """
    response_ias = {}
    user_ai_configs = AIClientConfiguration.objects.filter(token=user_token, enabled=True)
    
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_client, ai_config, processed_data, user_token): ai_config
            for ai_config in user_ai_configs
        }
        for future in as_completed(futures):
            ai_config, result = future.result()
            response_ias[ai_config.name] = result

    return response_ias
