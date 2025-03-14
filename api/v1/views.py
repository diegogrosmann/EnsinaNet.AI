"""Views para API v1.

Este módulo implementa os endpoints da versão 1 da API, incluindo
comparação de dados usando múltiplas IAs em paralelo.
"""

import logging
import time
import threading
from typing import Any
import dataclasses

from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework import status
from django.http import HttpRequest, HttpResponse
from datetime import timedelta

from core.exceptions import APICommunicationError, MissingAPIKeyError, APIError
from core.utils.doc_extractor import extract_text
from accounts.models import UserToken
from ai_config.models import (
    AIClientTokenConfig, 
    TrainingCapture, 
    AIClientConfiguration
)

from api.utils.queue_manager import QueueableTask, TaskQueue, TaskManager
from core.types import (
    AIComparisonResponse,
    AIMessage,
    AISingleComparisonData,
    AITrainingExample,
    APIComparisonResponse,
    JSONDict,
    QueueConfig,
    AIComparisonData,
    AIComparisonResponseCollection
)

logger = logging.getLogger(__name__)

def process_client(
    ai_config: AIClientConfiguration, 
    student_data: AISingleComparisonData, 
    student_id: str,
    user_token: UserToken
) -> AIComparisonResponse:
    """Processa a requisição para uma configuração de IA específica e um aluno.
    
    Args:
        ai_config: Configuração da IA a ser processada
        student_data: Dados processados contendo apenas instrutor e um aluno
        student_id: Identificador do aluno sendo processado
        user_token: Token do usuário
        
    Returns:
        AIComparisonResponse: Resultado do processamento com resposta e metadados
    """
    try:
        client = ai_config.create_api_client_instance(user_token)
        client_name = client.__class__.__name__
        logger.info(f"Processando requisição para {client_name} - Aluno: {student_id}")
        
        comparison_result, message = client.compare(student_data)
        
        logger.info(f"Comparação para {client_name} - Aluno: {student_id} realizada em {comparison_result.processing_time:.2f}s")
        
        # Manipula a captura de dados de treinamento
        handle_training_capture(
            user_token, 
            ai_config, 
            message, 
            comparison_result
        )
        
        # Retorna um dicionário ao invés de AIResponseData
        return comparison_result
        
    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_config.ai_client.api_client_class}: {e}")
        return AIComparisonResponse(
            response='',
            model_name=ai_config.model_name if ai_config.model_name else '',
            configurations=ai_config.configurations,
            processing_time=0.0,
            error="Chave de API não configurada"
        )
    except APICommunicationError as e:
        # Propaga erros de comunicação com a API para permitir retentativas
        logger.error(f"Erro de comunicação na API para {ai_config.ai_client.api_client_class}: {e}")
        raise
    except Exception as e:
        logger.exception(f"Erro ao processar {ai_config.ai_client.api_client_class} - Aluno: {student_id}:")
        return AIComparisonResponse(
            response='',
            model_name=ai_config.model_name if ai_config.model_name else '',
            configurations=ai_config.configurations,
            processing_time=0.0,
            error=str(e)
        )

def handle_training_capture(user_token: UserToken, ai_config: AIClientConfiguration, message: AIMessage, comparison_result: AIComparisonResponse) -> None:
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

        training_data = capture.get_examples_collection()
            
        training_data.add(
            AITrainingExample(
                message=message,
                response=comparison_result.response
            )
        )
        
        training_data.save()

        logger.info(f"Exemplo capturado para {ai_config.ai_client.api_client_class}")
    except TrainingCapture.DoesNotExist:
        pass

def process_request_data(data: JSONDict) -> JSONDict:
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
        request: Requisição HTTP com dados de comparação
        
    Returns:
        HttpResponse: Resultados das comparações por cada IA
    """
    version = request.version
    logger.info(f"Iniciando operação compare (API v{version})")
    
    # Extrai e valida token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    
    try:
        user_token = UserToken.objects.get(key=token_key)
        processed_data = process_request_data(request.data)
        
        # Converte para o tipo CompareRequestData e valida os campos obrigatórios
        compare_data = AIComparisonData(
            instructor = processed_data.get('instructor', {}),
            students = processed_data.get('students', {})
        )
        
        # Obtém configurações de IA ativas
        user_ai_configs = AIClientTokenConfig.objects.filter(
            token=user_token, 
            enabled=True
        ).select_related('ai_config', 'ai_config__ai_client')
        
        if not user_ai_configs.exists():
            raise APIError("Não há IAs ativas para este token", status_code=400)
            
        # Prepara a resposta estruturada
        response_data: AIComparisonResponseCollection = dict()
        results_lock = threading.Lock()
        
        # Inicializa o dicionário para cada aluno
        for student_id in compare_data.students.keys():
            response_data[student_id] = {}
        
        def store_result(config_data: AIClientConfiguration, 
                         value: Any, 
                         student_id: str) -> None:
            """Armazena resultado de forma thread-safe."""
            with results_lock:
                ai_name = config_data.name
                response_data[student_id][ai_name] = value
        
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
            
            queueConfig = QueueConfig(
                name=queue_name
            )

            queue = TaskQueue(
                config=queueConfig
            )
            
            # Adiciona tarefas para cada aluno e configuração
            for config in group['configs']:
                for student_id, student_data in compare_data.students.items():
                    student_payload = AISingleComparisonData(
                        instructor = compare_data.instructor,
                        student = student_data
                    )
                    
                    task = QueueableTask(
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
            f"{len(compare_data.students)} alunos, {len(user_ai_configs)} IAs"
        )
         
        response = APIComparisonResponse(
            success= True,
            data={
                'students': response_data,
            }
        )

        # Converte a dataclass para dicionário antes de passar para JsonResponse
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=status.HTTP_200_OK)
        
    except UserToken.DoesNotExist:
        logger.warning(f"Token inválido: {token_key}")
        response = APIComparisonResponse(success=False, error="Token inválido")
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception(f"Erro no processamento: {str(e)}")
        response = APIComparisonResponse(success=False, error=str(e))
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
