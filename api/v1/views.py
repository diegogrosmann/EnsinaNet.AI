import logging
import json
import time
from typing import Any, Dict, Tuple

from django.http import JsonResponse, HttpRequest, HttpResponse
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
def compare(request: HttpRequest) -> HttpResponse:
    """Realiza a comparação em lote utilizando múltiplos clientes de IA.

    Args:
        request (HttpRequest): Requisição HTTP contendo as informações do instrutor e dos alunos.

    Returns:
        HttpResponse: Resposta JSON com os resultados da comparação ou mensagem de erro.

    Raises:
        Exception: Caso o prompt não esteja configurado na configuração do usuário.
    """
    # Obtenha a versão definida na URL
    version = request.version  

    logger.info(f"Versão da API: {version}")
    logger.info("Iniciando operação compare em lote.")
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    try:
        user_token = UserToken.objects.get(key=token_key)
    except UserToken.DoesNotExist:
        logger.error("Token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)
    try:

        data = request.data
        if "students" not in data or "instructor" not in data:
            return JsonResponse({"error": "A solicitação deve conter 'students' e 'instructor'."},
                                status=status.HTTP_400_BAD_REQUEST)
    
        # NOVO: Verifica se o prompt está configurado no ai_configuration do usuário
        if not (hasattr(user_token, 'ai_configuration') and getattr(user_token.ai_configuration, 'prompt', None)):
            raise Exception("Prompt não configurado. Por favor, configure o prompt.")
        

        instructor_data = data["instructor"]
        students_data = data["students"]

        # Processa os dados do instrutor uma única vez.
        processed_instructor = process_request_data(instructor_data)
        batch_results: Dict[Any, Any] = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for student_id, student_data in students_data.items():
                payload = {
                    'instructor': processed_instructor,
                    'student': student_data
                }
                processed_payload = process_request_data(payload)
                futures[executor.submit(process_all_clients, processed_payload, user_token)] = student_id
            for future in as_completed(futures):
                student_id = futures[future]
                try:
                    result = future.result()
                    batch_results[student_id] = result
                except Exception as e:
                    logger.exception(f"Erro ao processar aluno {student_id}:")
                    batch_results[student_id] = {"error": str(e)}
        logger.info("Operação compare em lote finalizada com sucesso.")
        return JsonResponse({"students": batch_results}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("Erro na operação compare:")
        return JsonResponse({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def process_client(ai_config: AIClientConfiguration, processed_data: Dict[str, Any], user_token: UserToken) -> Tuple[AIClientConfiguration, Dict[str, Any]]:
    """Processa a requisição para uma configuração de IA específica.

    Args:
        ai_config (AIClientConfiguration): Configuração da IA a ser processada.
        processed_data (Dict[str, Any]): Dados processados da requisição.
        user_token (UserToken): Token do usuário que efetuou a requisição.

    Returns:
        Tuple[AIClientConfiguration, Dict[str, Any]]:
            Uma tupla contendo a configuração de IA e o resultado processado.

    Raises:
        MissingAPIKeyError: Se a chave de API estiver ausente.
        Exception: Em caso de outros erros durante o processamento.
    """
    try:
        start_time = time.perf_counter()
        if not ai_config.enabled:
            logger.info(f"{ai_config.name} desabilitada para este token.")
            return ai_config, {"message": "IA desabilitada."}
        config = AIClientConfig(
            api_key=ai_config.ai_client.api_key,
            api_url=ai_config.ai_client.api_url,
            model_name=getattr(ai_config, 'trained_model_name', None) or ai_config.model_name,
            configurations=ai_config.configurations.copy(),
            base_instruction=user_token.ai_configuration.base_instruction or "",
            prompt=user_token.ai_configuration.prompt or "",
            responses=user_token.ai_configuration.responses or "",
            enabled=ai_config.enabled,
            use_system_message=ai_config.use_system_message  # NOVO: repassa a opção para o cliente
        )
        training_file = user_token.ai_configuration.training_file.file if user_token.ai_configuration.training_file else None
        if training_file:
            processed_data['training_file'] = training_file
        client_class = AI_CLIENT_MAPPING.get(ai_config.ai_client.api_client_class)
        if not client_class:
            raise APICommunicationError(f"Cliente '{ai_config.ai_client.api_client_class}' não mapeado.")
        ai_client_instance = client_class(config)
        comparison_result, system_message, user_message = ai_client_instance.compare(processed_data)
        handle_training_capture(user_token, ai_config.ai_client, system_message, user_message, comparison_result)
        processing_time = round(time.perf_counter() - start_time, 2)
        result = {
            "response": comparison_result,
            "model_name": config.model_name,
            "configurations": config.configurations,
            "processing_time": processing_time,
        }
        return ai_config, result
    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_config.ai_client.api_client_class}: {e}")
        return ai_config, {"error": "Chave de API não configurada."}
    except Exception as e:
        logger.exception(f"Erro ao processar {ai_config.ai_client.api_client_class}:")
        return ai_config, {"error": str(e)}


def handle_training_capture(user_token: UserToken, ai_client: Any, system_message: str, user_message: str, comparison_result: str) -> None:
    """Gerencia a captura de dados de treinamento, adicionando exemplos ao arquivo se houver captura ativa.

    Args:
        user_token (UserToken): Token do usuário.
        ai_client (Any): Instância do cliente de IA.
        system_message (str): Mensagem retornada pelo sistema.
        user_message (str): Mensagem retornada ao usuário.
        comparison_result (str): Resultado da comparação efetuada.

    Returns:
        None
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
                'response': comparison_result,
            })
            with capture.temp_file.open('w') as f:
                json.dump(training_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Exemplo capturado para {ai_client.api_client_class}")
    except TrainingCapture.DoesNotExist:
        pass


def process_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa os dados recursivamente para extrair texto de arquivos quando o campo 'type' é 'file'.

    Args:
        data (Dict[str, Any]): Dados originais da requisição.

    Returns:
        Dict[str, Any]: Dados com o conteúdo dos arquivos extraído.
    """
    def process_file_content(obj: Any) -> None:
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


def process_all_clients(processed_data: Dict[str, Any], user_token: UserToken) -> Dict[str, Any]:
    """Processa a requisição para todos os clientes de IA vinculados ao token.

    Args:
        processed_data (Dict[str, Any]): Dados da requisição já processados.
        user_token (UserToken): Token do usuário efetuando a requisição.

    Returns:
        Dict[str, Any]: Dicionário com os resultados indexados pelo nome da configuração.
    """
    results: Dict[str, Any] = {}
    user_ai_configs = AIClientConfiguration.objects.filter(token=user_token, enabled=True)
    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_client, config, processed_data, user_token): config
            for config in user_ai_configs
        }
        for future in as_completed(futures):
            ai_config, result = future.result()
            results[ai_config.name] = result
    return results
