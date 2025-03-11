"""Views para API v1.

Este módulo implementa os endpoints da versão 1 da API, incluindo
comparação de dados usando múltiplas IAs em paralelo.
"""

import logging
import json
import time
import threading
from typing import Any, Dict, Optional, List
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework import status
from django.http import HttpRequest, HttpResponse

from core.exceptions import APICommunicationError, MissingAPIKeyError
from accounts.models import UserToken
from ai_config.models import (
    AIClientTokenConfig, 
    TrainingCapture, 
    AIClientConfiguration
)
from api.utils.doc_extractor import extract_text
from api.utils.queue_manager import Task, TaskQueue, TaskManager

logger = logging.getLogger(__name__)

def validate_request_data(data: Dict[str, Any]) -> Optional[JsonResponse]:
    """Valida os dados da requisição.
    
    Args:
        data: Dados recebidos na requisição.
        
    Returns:
        Optional[JsonResponse]: Resposta de erro se dados inválidos, None se válidos.
    """
    if 'instructor' not in data or 'students' not in data:
        return JsonResponse({
            "error": "Dados inválidos. É necessário fornecer 'instructor' e 'students'"
        }, status=status.HTTP_400_BAD_REQUEST)

    students_data = data.get('students', {})
    if not isinstance(students_data, dict) or not students_data:
        return JsonResponse({
            "error": "Dados de alunos inválidos ou vazios"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return None

def process_training_capture(capture: TrainingCapture, example_data: Dict[str, Any]) -> None:
    """Processa e salva um exemplo para captura de treinamento.
    
    Args:
        capture: Objeto de captura ativa.
        example_data: Dados do exemplo a ser salvo.
    """
    try:
        with capture.temp_file.open('r') as f:
            training_data = json.load(f)
    except json.JSONDecodeError:
        training_data = []
        
    training_data.append(example_data)
    
    with capture.temp_file.open('w') as f:
        json.dump(training_data, f, ensure_ascii=False, indent=4)
    logger.debug("Exemplo capturado com sucesso")

def process_client(ai_config: AIClientConfiguration = None, 
                   student_data: Dict[str, Any] = None, 
                   student_id: str = None,
                   user_token: UserToken = None) -> Dict[str, Any]:
    """Processa a requisição para uma configuração de IA específica e um aluno específico.
    
    Args:
        ai_config: Configuração da IA a ser processada
        student_data: Dados processados contendo apenas instrutor e um aluno
        student_id: Identificador do aluno sendo processado
        user_token: Token do usuário
        
    Returns:
        Dict[str, Any]: Resultado do processamento
    """
    try:
        client_name = ai_config.ai_client.api_client_class
        logger.info(f"Processando requisição para {client_name} - Aluno: {student_id}")
        
        # Verifica se a configuração de IA tem uma chave API válida
        if not ai_config.ai_client.api_key:
            raise MissingAPIKeyError(f"Chave de API não configurada para {client_name}")
        
        # Realiza a chamada à API
        start_time = time.time()
        comparison_result, system_message, user_message = ai_config.compare(student_data, user_token)
        elapsed_time = time.time() - start_time
        
        logger.info(f"Comparação para {client_name} - Aluno: {student_id} realizada em {elapsed_time:.2f}s")
        
        # Manipula a captura de dados de treinamento
        handle_training_capture(user_token, ai_config, system_message, user_message, comparison_result)
        
        # Retorna informações adicionais no formato desejado
        return {
            "response": comparison_result,
            "model_name": ai_config.model_name,
            "configurations": ai_config.configurations,
            "processing_time": round(elapsed_time, 3)
        }
        
    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_config.ai_client.api_client_class}: {e}")
        return {"error": "Chave de API não configurada"}
    except APICommunicationError as e:
        # Propaga erros de comunicação com a API para permitir retentativas
        logger.error(f"Erro de comunicação na API para {ai_config.ai_client.api_client_class}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Erro ao processar {ai_config.ai_client.api_client_class} - Aluno: {student_id}:")
        return {"error": str(e)}
    
def handle_training_capture(user_token: UserToken, ai_config: AIClientConfiguration, system_message: str, user_message: str, comparison_result: str) -> None:
    """Gerencia a captura de dados de treinamento, adicionando exemplos ao arquivo se houver captura ativa."""
    try:
        capture = TrainingCapture.objects.get(
            token=user_token,
            ai_client_config=ai_config,
            is_active=True
        )

        # Usa o timeout configurado no perfil do usuário
        timeout_minutes = user_token.user.profile.capture_inactivity_timeout
        if timezone.now() - capture.last_activity > timedelta(minutes=timeout_minutes):
            logger.info(f"Captura expirada para {ai_config.ai_client.api_client_class} - Removendo...")
            capture.delete()
            return

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
        logger.info(f"Exemplo capturado para {ai_config.ai_client.api_client_class}")
    except TrainingCapture.DoesNotExist:
        pass

def process_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa os dados recursivamente para extrair texto de arquivos quando o campo 'type' é 'file'."""
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

@api_view(['POST'])
def compare(request: HttpRequest) -> HttpResponse:
    """Endpoint para comparação de dados usando múltiplas IAs.
    
    Recebe dados de instrutor e alunos, processa em paralelo usando
    as IAs configuradas e retorna os resultados comparados.
    
    Args:
        request: Requisição HTTP com dados a serem comparados.
        
    Returns:
        HttpResponse: Resultados das comparações por cada IA.
    """
    version = request.version
    logger.info(f"Iniciando operação compare (API v{version})")
    
    # Extrai e valida token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    
    try:
        user_token = UserToken.objects.get(key=token_key)
        processed_data = process_request_data(request.data)
        
        # Valida dados da requisição
        error_response = validate_request_data(processed_data)
        if error_response:
            return error_response
            
        instructor_data = processed_data['instructor']
        students_data = processed_data['students']
        
        # Obtém configurações de IA ativas
        user_ai_configs = AIClientTokenConfig.objects.filter(
            token=user_token, 
            enabled=True
        ).select_related('ai_config', 'ai_config__ai_client')
        
        if not user_ai_configs.exists():
            return JsonResponse({
                "error": "Não há configurações de IA ativas para este token"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Configuração para processamento paralelo
        results = {student_id: {} for student_id in students_data.keys()}
        results_lock = threading.Lock()
        
        def store_result(config_data: AIClientConfiguration, 
                        value: Any, 
                        student_id: str) -> None:
            """Armazena resultado de forma thread-safe."""
            with results_lock:
                ai_name = config_data.ai_client.api_client_class
                results[student_id][ai_name] = value
        
        # Agrupa configurações por cliente global
        configs_by_global = {}
        for config in user_ai_configs:
            global_config_id = config.ai_config.ai_client.id
            global_client_class = config.ai_config.ai_client.name
            if global_config_id not in configs_by_global:
                configs_by_global[global_config_id] = {
                    'name': global_client_class,
                    'configs': []
                }
            configs_by_global[global_config_id]['configs'].append(config)
        
        # Configura gerenciador de tarefas
        manager = TaskManager()
        
        # Cria filas de processamento
        for global_id, group in configs_by_global.items():
            queue_name = f"queue_{group['name']}_{global_id}"
            logger.info(
                f"Criando fila '{queue_name}' com {len(group['configs'])} configurações"
            )
            
            queue = TaskQueue(
                name=queue_name,
                max_attempts=3,
                initial_wait=30,
                backoff_factor=2,
                randomness_factor=0.2,
                max_parallel_first=-1,
                max_parallel_retry=1
            )
            
            # Adiciona tarefas para cada aluno e configuração
            for config in group['configs']:
                for student_id, student_data in students_data.items():
                    student_payload = {
                        "instructor": instructor_data,
                        "student": student_data
                    }
                    
                    task = Task(
                        identifier=f"{config.ai_config.name}",
                        func=process_client,
                        args=(config.ai_config, student_payload, student_id, user_token),
                        result_callback=lambda key, value, sid=student_id, cfg=config.ai_config: store_result(cfg, value, sid)
                    )
                    queue.add_task(task)
            
            manager.add_queue(queue)
        
        # Executa processamento
        start_time = time.time()
        manager.run()
        elapsed = time.time() - start_time
        
        logger.info(
            f"Processamento concluído em {elapsed:.2f}s - "
            f"{len(students_data)} alunos, {len(user_ai_configs)} IAs"
        )
        
        return JsonResponse({"students": results}, status=status.HTTP_200_OK)
        
    except UserToken.DoesNotExist:
        logger.warning(f"Token inválido: {token_key}")
        return JsonResponse({
            "error": "Token inválido"
        }, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception(f"Erro no processamento: {str(e)}")
        return JsonResponse({
            "error": f"Erro ao processar requisição: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





