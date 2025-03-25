"""Views para API v1.

Este módulo implementa os endpoints da versão 1 da API, incluindo
comparação de dados usando múltiplas IAs em paralelo.
"""

import logging
import time
import threading
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union
import dataclasses
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework import status
from django.http import HttpRequest, HttpResponse

from core.exceptions import (
    APICommunicationError, 
    MissingAPIKeyError, 
    APIError, 
    FileProcessingError,
    ApplicationError,
    TrainingError
)
from core.utils.doc_extractor import extract_text
from accounts.models import UserToken
from ai_config.models import (
    AIClientTokenConfig, 
    TrainingCapture, 
    AIClientConfiguration
)

from api.utils.queue_manager import TaskQueue, TaskManager
from core.types.task import QueueableTask, QueueConfig
from core.types.base import JSONDict
from core.types.api_response import APIComparisonAPIResponse
from core.types.comparison import (
    AIComparisonData,
    AISingleComparisonData,
    AIComparisonResponse, 
    AIComparisonResponseCollection
)
from core.types.messaging import AIMessage
from core.types.async_task import AsyncComparisonTask, AsyncTaskStatus
from api.utils.async_tasks import submit_task, get_task, update_task
from api.tasks import process_comparison_task

logger = logging.getLogger(__name__)

def process_client(
    ai_config: AIClientConfiguration, 
    student_data: AISingleComparisonData, 
    student_id: str,
    user_token: UserToken
) -> AIComparisonResponse:
    """Processa a requisição para uma configuração de IA específica e um aluno.
    
    Envia os dados de comparação para um cliente de IA específico e obtém
    a resposta da comparação entre instrutor e aluno. Também gerencia
    a captura de exemplos de treinamento, caso esteja configurada.
    
    Args:
        ai_config: Configuração da IA a ser utilizada
        student_data: Dados de comparação contendo instrutor e um aluno
        student_id: Identificador do aluno sendo processado
        user_token: Token do usuário autenticado
        
    Returns:
        AIComparisonResponse: Resultado do processamento com resposta e metadados
        
    Raises:
        MissingAPIKeyError: Se não houver chave de API configurada
        APICommunicationError: Se ocorrer erro na comunicação com a API externa
    """
    try:
        client_name = ai_config.ai_client.api_client_class
        logger.info(f"Processando requisição para {client_name} - Aluno: {student_id}")
        
        # Cria instância do cliente de IA
        client = ai_config.create_api_client_instance(user_token)
        client_name = client.__class__.__name__
        logger.debug(f"Cliente {client_name} instanciado com sucesso")
        
        # Processa a comparação
        start_time = time.time()
        comparison_result, message = client.compare(student_data)
        elapsed_time = time.time() - start_time
        
        logger.info(f"Comparação para {client_name} - Aluno: {student_id} "
                    f"concluída em {elapsed_time:.3f}s")
        
        # Manipula a captura de dados de treinamento
        handle_training_capture(
            user_token=user_token, 
            ai_config=ai_config, 
            message=message, 
            comparison_result=comparison_result
        )
        
        # Retorna o resultado da comparação
        return comparison_result
        
    except MissingAPIKeyError as e:
        logger.error(f"Chave de API ausente para {ai_config.ai_client.api_client_class}: {str(e)}")
        return AIComparisonResponse(
            model_name=ai_config.ai_client.api_client_class,
            configurations={},
            processing_time=0.0,
            error=str(e)
        )
    except APICommunicationError as e:
        # Propaga erros de comunicação com a API para permitir retentativas
        logger.error(f"Erro de comunicação na API para {ai_config.ai_client.api_client_class}: {str(e)}")
        raise
    except Exception as e:
        logger.exception(f"Erro não esperado ao processar {ai_config.ai_client.api_client_class} - Aluno: {student_id}")
        return AIComparisonResponse(
            model_name=ai_config.ai_client.api_client_class,
            configurations={},
            processing_time=0.0,
            error=f"Erro interno: {str(e)}"
        )

def handle_training_capture(
    user_token: UserToken, 
    ai_config: AIClientConfiguration, 
    message: AIMessage, 
    comparison_result: AIComparisonResponse
) -> None:
    """Gerencia a captura de dados de treinamento.
    
    Se houver captura ativa, adiciona o exemplo atual ao arquivo 
    de captura de treinamento associado ao token e configuração.
    
    Args:
        user_token: Token do usuário autenticado
        ai_config: Configuração da IA utilizada
        message: Mensagens usadas na requisição
        comparison_result: Resultado da comparação
        
    Raises:
        TrainingError: Se ocorrer erro durante o processo de captura
    """
    try:
        try:
            # Verifica se existe uma captura ativa para este token e configuração
            capture = TrainingCapture.objects.get(
                token=user_token,
                ai_client_config=ai_config,
                is_active=True
            )
            
            # Se existe uma captura ativa e temos uma resposta (sem erro), registrar o exemplo
            if not comparison_result.error and comparison_result.response:
                # Adiciona o exemplo à coleção
                from core.types.training import AITrainingExample
                example = AITrainingExample(
                    system_message=message.system_message,
                    user_message=message.user_message,
                    response=comparison_result.response
                )
                
                # Registra o exemplo no arquivo de captura
                capture.add_example(example)
                logger.info(f"Exemplo adicionado à captura de treinamento {capture.id}")
                
        except TrainingCapture.DoesNotExist:
            # Sem captura ativa, prossegue normalmente
            pass
            
    except Exception as e:
        # Log do erro, mas não propaga para não interromper a resposta principal
        logger.error(f"Erro durante captura de treinamento: {str(e)}", exc_info=True)
        # Não propaga a exceção para não interromper o fluxo principal
        

def process_request_data(data: JSONDict) -> JSONDict:
    """Processa os dados recursivamente para extrair texto de documentos.
    
    Percorre a estrutura de dados buscando campos do tipo 'file' e 
    converte seu conteúdo para texto utilizando o extrator apropriado.
    
    Args:
        data: Dicionário com dados da requisição
        
    Returns:
        JSONDict: Dados processados com arquivos convertidos para texto
        
    Raises:
        FileProcessingError: Se houver erro no processamento de algum arquivo
    """
    logger.debug("Iniciando processamento de dados da requisição")
    
    def process_file_content(obj: Any) -> None:
        """Função auxiliar recursiva para processar conteúdo de arquivos."""
        if isinstance(obj, dict):
            # Se for um objeto de arquivo, extrair o texto
            if "type" in obj and obj["type"] == "file" and "content" in obj:
                logger.debug(f"Arquivo detectado: {obj.get('name', 'sem nome')}")
                # Extrai o texto do arquivo
                file_text = extract_text(obj)
                # Substitui o objeto do arquivo pelo texto extraído
                obj["type"] = "text"
                obj["content"] = file_text
                if "name" in obj:
                    obj["filename"] = obj.pop("name")
            else:
                # Processar cada campo do dicionário recursivamente
                for key, value in obj.items():
                    process_file_content(value)
        elif isinstance(obj, list):
            # Processar cada item da lista recursivamente
            for item in obj:
                process_file_content(item)
                
    try:
        processed = data.copy()
        process_file_content(processed)
        return processed
    except FileProcessingError:
        # Repassar exceções específicas
        raise
    except Exception as e:
        logger.error(f"Erro não esperado ao processar dados: {str(e)}", exc_info=True)
        raise APIError(f"Erro ao processar dados da requisição: {str(e)}")

@api_view(['POST'])
def compare(request: HttpRequest, is_async: bool = False) -> HttpResponse:
    """Endpoint para comparação de dados usando múltiplas IAs.
    
    Recebe dados de instrutor e alunos, processa em paralelo usando
    as IAs configuradas para o token do usuário e retorna os resultados
    comparados de todas as IAs para todos os alunos.
    
    Args:
        request: Requisição HTTP com dados de comparação
        is_async: Indica se é uma chamada assíncrona interna
        
    Returns:
        HttpResponse: Resultados das comparações por cada IA para cada aluno
        
    Raises:
        APIError: Se ocorrer erro no processamento
    """
    version = request.version
    logger.info(f"Iniciando operação compare (API v{version})")
    
    # Extrai e valida token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    
    try:
        # Busca o token do usuário
        user_token = UserToken.objects.get(key=token_key)
        logger.debug(f"Token validado para usuário: {user_token.user.username}")
        
        # Processa os dados da requisição (incluindo arquivos)
        processed_data = process_request_data(request.data)
        
        # Converte para o tipo CompareRequestData e valida os campos obrigatórios
        compare_data = AIComparisonData(
            instructor=processed_data.get('instructor', {}),
            students=processed_data.get('students', {})
        )
        
        logger.info(f"Dados de comparação validados: {len(compare_data.students)} alunos")
        
        # Obtém configurações de IA ativas para o token
        user_ai_configs = AIClientTokenConfig.objects.filter(
            token=user_token,
            enabled=True
        ).select_related('ai_config', 'ai_config__ai_client')
        
        if not user_ai_configs.exists():
            logger.warning(f"Sem configurações de IA ativas para o token: {user_token}")
            raise APIError("Sem configurações de IA ativas para este token", status_code=400)
            
        logger.info(f"Encontradas {user_ai_configs.count()} configurações de IA ativas")
        
        # Prepara a resposta estruturada
        response_data: AIComparisonResponseCollection = dict()
        results_lock = threading.Lock()
        
        # Inicializa o dicionário para cada aluno
        for student_id in compare_data.students.keys():
            response_data[student_id] = dict()
        
        def store_result(config_data: AIClientConfiguration, 
                         student_id: str, 
                         result: AIComparisonResponse) -> None:
            """Armazena o resultado de uma comparação no dicionário de respostas."""
            with results_lock:
                client_name = config_data.ai_client.api_client_class
                response_data[student_id][client_name] = result
        
        # Agrupa configurações por cliente global
        configs_by_global = {}
        for config in user_ai_configs:
            global_id = config.ai_config.ai_client.id
            if global_id not in configs_by_global:
                configs_by_global[global_id] = []
            configs_by_global[global_id].append(config.ai_config)
        
        # Configura gerenciador de tarefas
        manager = TaskManager()
        logger.debug("TaskManager inicializado")
        
        # Cria filas de processamento
        for global_id, group in configs_by_global.items():
            queue_config = QueueConfig(
                name=f"comp_{global_id}",
                max_attempts=2,
                initial_wait=1.0,
                backoff_factor=2.0,
                max_parallel_first=3,
                max_parallel_retry=1
            )
            
            queue = TaskQueue(queue_config)
            
            # Adiciona tarefas para cada combinação de aluno e configuração
            for student_id, student_data in compare_data.students.items():
                for config in group:
                    # Cria dados para a comparação individual
                    single_data = AISingleComparisonData(
                        instructor=compare_data.instructor,
                        student=student_data,
                        student_id=student_id
                    )
                    
                    # Cria uma tarefa para esta comparação
                    task = QueueableTask(
                        func=process_client,
                        args=(config, single_data, student_id, user_token),
                        result_callback=lambda tid, res, sid=student_id, cfg=config: store_result(cfg, sid, res)
                    )
                    
                    # Adiciona à fila de processamento
                    queue.add_task(task)
            
            # Adiciona a fila ao gerenciador
            manager.add_queue(queue)

        # Executa processamento
        logger.info("Iniciando processamento paralelo das tarefas")
        start_time = time.time()
        manager.run()
        elapsed = time.time() - start_time
        
        logger.info(
            f"Processamento paralelo concluído em {elapsed:.2f}s - "
            f"{len(compare_data.students)} alunos com {user_ai_configs.count()} IAs"
        )
         
        # Constrói a resposta usando o tipo explícito APIComparisonAPIResponse
        response = APIComparisonAPIResponse.create_successful_comparison(response_data)

        # Converte a dataclass para dicionário antes de passar para JsonResponse
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=status.HTTP_200_OK)
        
    except UserToken.DoesNotExist:
        logger.warning(f"Token inválido: {token_key}")
        response = APIComparisonAPIResponse(success=False, error="Token inválido")
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=status.HTTP_401_UNAUTHORIZED)
    except APIError as e:
        # Repassa erro com status code específico
        logger.error(f"APIError: {e.status_code} - {str(e)}")
        response = APIComparisonAPIResponse(success=False, error=str(e))
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=e.status_code)
    except Exception as e:
        logger.exception(f"Erro não tratado na operação compare: {str(e)}")
        response = APIComparisonAPIResponse(success=False, error=f"Erro interno: {str(e)}")
        response_dict = dataclasses.asdict(response)
        return JsonResponse(response_dict, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def async_compare(request: HttpRequest) -> HttpResponse:
    """Endpoint para comparação assíncrona de dados usando múltiplas IAs.
    
    Recebe dados de instrutor e alunos, cria uma tarefa assíncrona e 
    retorna um identificador para consulta posterior dos resultados.
    
    Args:
        request: Requisição HTTP com dados de comparação
        
    Returns:
        HttpResponse: Identificador da tarefa criada
        
    Raises:
        APIError: Se ocorrer erro no processamento inicial
    """
    version = request.version
    logger.info(f"Iniciando operação de comparação assíncrona (API v{version})")
    
    # Extrai e valida token
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    
    try:
        # Busca o token do usuário
        user_token = UserToken.objects.get(key=token_key)
        logger.debug(f"Token validado para usuário: {user_token.user.username}")
        
        # Processa os dados da requisição (incluindo arquivos)
        processed_data = process_request_data(request.data)
        
        # Valida os dados de entrada
        compare_data = AIComparisonData(
            instructor=processed_data.get('instructor', {}),
            students=processed_data.get('students', {})
        )
        
        # Verifica se há IAs disponíveis para o token
        user_ai_configs = AIClientTokenConfig.objects.filter(
            token=user_token,
            enabled=True
        ).select_related('ai_config', 'ai_config__ai_client')
        
        if not user_ai_configs.exists():
            raise APIError("Sem configurações de IA ativas para este token", status_code=400)
        
        # Criar tarefa assíncrona
        expiration = datetime.now() + timedelta(hours=24)
        task = AsyncComparisonTask(
            input_data=processed_data,
            user_id=user_token.user_id,
            user_token_id=user_token.id,
            expiration=expiration
        )
        
        # Define o tempo máximo que a tarefa ficará disponível
        ttl = 86400  # 24 horas em segundos
        
        # Registra a tarefa no cache
        submit_task(task, ttl)
        
        # Inicia o processamento assíncrono
        process_comparison_task.delay(task.task_id, token_key)
        
        logger.info(f"Tarefa assíncrona {task.task_id} registrada para usuário {user_token.user.username}")
        
        # Retorna o identificador da tarefa
        return JsonResponse({
            'success': True,
            'task_id': task.task_id,
            'expires_at': task.expiration.isoformat() if task.expiration else None
        }, status=status.HTTP_202_ACCEPTED)
        
    except UserToken.DoesNotExist:
        logger.warning(f"Token inválido: {token_key}")
        return JsonResponse({
            'success': False,
            'error': 'Token inválido'
        }, status=status.HTTP_401_UNAUTHORIZED)
    except APIError as e:
        logger.error(f"APIError: {e.status_code} - {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=e.status_code)
    except Exception as e:
        logger.exception(f"Erro não tratado na operação async_compare: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f"Erro interno: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def async_compare_status(request: HttpRequest, task_id: str) -> HttpResponse:
    """Verifica o status de uma tarefa de comparação assíncrona.
    
    Args:
        request: Requisição HTTP.
        task_id: Identificador da tarefa a ser verificada.
        
    Returns:
        HttpResponse: Status atual da tarefa e resultado (se concluída)
    """
    try:
        # Extrai e valida token
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
        
        # Busca o token do usuário
        user_token = UserToken.objects.get(key=token_key)
        
        # Recupera a tarefa
        task = get_task(task_id)
        
        if not task:
            return JsonResponse({
                'success': False,
                'error': f"Tarefa não encontrada: {task_id}"
            }, status=status.HTTP_404_NOT_FOUND)
            
        # Verifica se o usuário tem permissão para acessar esta tarefa
        if task.user_id != user_token.user_id:
            return JsonResponse({
                'success': False,
                'error': "Sem permissão para acessar esta tarefa"
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Retorna o status atual
        response = {
            'success': True,
            'task_id': task_id,
            'status': str(task.status),
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat()
        }
        
        # Se concluída com sucesso, incluir resultado
        if task.status == AsyncTaskStatus.COMPLETED and task.result:
            response['result'] = task.result
            
        # Se falhou, incluir mensagem de erro
        elif task.status == AsyncTaskStatus.FAILED and task.error:
            response['error_message'] = task.error
            
        return JsonResponse(response, status=status.HTTP_200_OK)
        
    except UserToken.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido'
        }, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        logger.exception(f"Erro ao verificar status de tarefa assíncrona {task_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f"Erro ao verificar status da tarefa: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
