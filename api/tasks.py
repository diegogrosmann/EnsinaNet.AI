"""
Tasks Celery para processamento assíncrono da API.

Define tarefas que serão processadas em segundo plano pelo Celery,
como comparações assíncronas e outras operações de longa duração.
"""
import logging
import time
import json
import threading
from typing import Dict, Any

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from accounts.models import UserToken
from ai_config.models import AIClientTokenConfig
from core.exceptions import APIError

from api.utils.async_tasks import get_task, update_task, store_task_result
from api.utils.queue_manager import TaskQueue, TaskManager
from api.models import APILog
from core.types.async_task import AsyncTaskStatus
from core.types.base import JSONDict
from core.types.task import QueueableTask, QueueConfig
from core.types.comparison import (
    AIComparisonData,
    AISingleComparisonData,
    AIComparisonResponse, 
    AIComparisonResponseCollection
)

# Modificação do logger para usar o namespace que direciona para tasks.log
logger = logging.getLogger('ai_config.tasks')

@shared_task(
    bind=True, 
    name="process_comparison_task",
    max_retries=3,
    default_retry_delay=300
)
def process_comparison_task(self, task_id: str, token_key: str) -> JSONDict:
    """Processa uma comparação assíncrona em segundo plano.
    
    Args:
        task_id: Identificador único da tarefa
        token_key: Chave do token de autenticação
        
    Returns:
        JSONDict contendo informações sobre o processamento
        
    Raises:
        Exception: Em caso de falha no processamento
    """
    logger.info(f"[TASK:{task_id}] Iniciando processamento assíncrono - token: {token_key[:5]}***")
    task = None
    
    try:
        # Recupera a tarefa
        task = get_task(task_id)
        if not task:
            error_msg = f"Tarefa não encontrada: {task_id}"
            logger.error(f"[TASK:{task_id}] {error_msg}")
            return {"success": False, "error": error_msg}
        
        logger.info(f"[TASK:{task_id}] Tarefa recuperada com sucesso. Status atual: {task.status}")
        
        # Atualiza status para processando
        task.update_status(AsyncTaskStatus.PROCESSING)
        update_task(task)
        logger.debug(f"[TASK:{task_id}] Status atualizado para PROCESSING")
        
        # Verifica token
        try:
            user_token = UserToken.objects.get(key=token_key)
            logger.debug(f"[TASK:{task_id}] Token verificado para usuário: {user_token.user.username}")
        except UserToken.DoesNotExist:
            error_msg = "Token inválido ou expirado"
            logger.error(f"[TASK:{task_id}] {error_msg}")
            task.set_failure(error_msg)
            update_task(task)
            return {"success": False, "error": error_msg}
        
        # Processa os dados
        try:
            # Importamos as funções necessárias
            from api.v1.views import process_client, process_request_data  
            
            # Processa os dados da requisição (incluindo arquivos)
            processed_data = process_request_data(task.input_data)
            
            # Converte para o tipo CompareRequestData e valida os campos
            compare_data = AIComparisonData(
                instructor=processed_data.get('instructor', {}),
                students=processed_data.get('students', {})
            )
            
            logger.info(f"[TASK:{task_id}] Dados de comparação validados: {len(compare_data.students)} alunos")
            
            # Obtém configurações de IA ativas para o token
            user_ai_configs = AIClientTokenConfig.objects.filter(
                token=user_token,
                enabled=True
            ).select_related('ai_config', 'ai_config__ai_client')
            
            if not user_ai_configs.exists():
                error_msg = "Sem configurações de IA ativas para este token"
                logger.warning(f"[TASK:{task_id}] {error_msg}")
                task.set_failure(error_msg)
                update_task(task)
                return {"success": False, "error": error_msg}
                
            logger.info(f"[TASK:{task_id}] Encontradas {user_ai_configs.count()} configurações de IA ativas")
            
            # Prepara a resposta estruturada
            response_data: Dict[str, Dict[str, Dict]] = dict()
            results_lock = threading.Lock()
            
            # Inicializa o dicionário para cada aluno
            for student_id in compare_data.students.keys():
                response_data[student_id] = dict()
            
            def store_result(config_data, student_id, result):
                """Armazena o resultado de uma comparação no dicionário de respostas."""
                with results_lock:
                    client_name = config_data.ai_client.api_client_class
                    # Converte o objeto AIComparisonResponse para dicionário antes de armazenar
                    response_data[student_id][client_name] = result.to_dict() if hasattr(result, 'to_dict') else result
            
            # Agrupa configurações por cliente global
            configs_by_global = {}
            for config in user_ai_configs:
                global_id = config.ai_config.ai_client.id
                if global_id not in configs_by_global:
                    configs_by_global[global_id] = []
                configs_by_global[global_id].append(config.ai_config)
            
            # Configura gerenciador de tarefas
            manager = TaskManager()
            logger.debug(f"[TASK:{task_id}] TaskManager inicializado")
            
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
                        task_item = QueueableTask(
                            func=process_client,
                            args=(config, single_data, student_id, user_token),
                            result_callback=lambda tid, res, sid=student_id, cfg=config: store_result(cfg, sid, res)
                        )
                        
                        # Adiciona à fila de processamento
                        queue.add_task(task_item)
                
                # Adiciona a fila ao gerenciador
                manager.add_queue(queue)

            # Executa processamento
            logger.info(f"[TASK:{task_id}] Iniciando processamento paralelo das tarefas")
            start_time = time.time()
            manager.run()
            elapsed = time.time() - start_time
            
            logger.info(
                f"[TASK:{task_id}] Processamento paralelo concluído em {elapsed:.2f}s - "
                f"{len(compare_data.students)} alunos com {user_ai_configs.count()} IAs"
            )
            
            # Verifica e converte qualquer objeto que não seja JSON serializable
            def ensure_serializable(obj):
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                elif isinstance(obj, dict):
                    return {k: ensure_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [ensure_serializable(item) for item in obj]
                return obj
            
            # Garante que toda a estrutura de resposta seja serializável
            serializable_response = ensure_serializable(response_data)
            
            # Armazena o resultado
            result_data = {
                "success": True,
                "data": {
                    "students": serializable_response
                }
            }
            store_task_result(task_id, result=result_data)
            
            logger.info(f"[TASK:{task_id}] Processamento concluído com sucesso")
            return {"success": True, "task_id": task_id}
            
        except Exception as e:
            logger.exception(f"[TASK:{task_id}] Erro ao processar comparação: {str(e)}")
            task.set_failure(f"Erro no processamento: {str(e)}")
            update_task(task)
            return {"success": False, "error": str(e)}
            
    except Exception as e:
        logger.exception(f"[TASK:{task_id}] Erro crítico no processamento assíncrono: {str(e)}")
        if task:
            try:
                task.set_failure(f"Erro no processamento: {str(e)}")
                update_task(task)
            except Exception:
                logger.exception(f"[TASK:{task_id}] Erro ao atualizar status da tarefa após falha")
        
        # Tenta retentar a tarefa se ainda houver tentativas disponíveis
        try:
            self.retry(exc=e)
        except Exception as retry_error:
            logger.error(f"[TASK:{task_id}] Erro ao agendar retry: {str(retry_error)}")
            
        return {"success": False, "error": str(e)}
