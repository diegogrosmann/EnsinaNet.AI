import logging
import threading
import time
import uuid

from api.exceptions import (
    MissingAPIKeyException, 
    APICommunicationException, 
    APIClientException
)
from api.tasks.comparison import process_comparison_job
from core.exceptions import FileProcessingException
from api.service.training import handle_training_capture

from core.models.operations import Operation
from core.types import (
    JSONDict,
    APPResponse,
    SingleComparisonRequestData
)

from ai_config.models import AIClientConfiguration, AIClientTokenConfig
from accounts.models import UserToken

from core.types.ai import AIResponseDict
from core.types.base import DataModel
from core.types.comparison import AsyncComparisonTask, ComparisonDict, ComparisonRequestData, ComparisonJob, ComparisonTask
from core.types.operation import OperationData
from core.types.task import AsyncTask, QueueConfig, QueueableTask
from core.types.status import EntityStatus
from core.utils.doc_extractor import extract_text
from core.utils.queue_manager import TaskManager, TaskQueue

logger = logging.getLogger(__name__)

def process_client(
    ai_config: AIClientConfiguration, 
    student_data: SingleComparisonRequestData, 
    student_id: str,
    user_token: UserToken
) -> APPResponse:
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
        
        handle_training_capture(
            user_token=user_token, 
            ai_config=ai_config, 
            message=message, 
            comparison_result=comparison_result
        )
        
        return comparison_result
        
    except MissingAPIKeyException as e:
        logger.error(f"Chave de API ausente para {ai_config.ai_client.api_client_class}: {str(e)}")
        return APPResponse(
            model_name=ai_config.ai_client.api_client_class,
            configurations={},
            processing_time=0.0,
            error=str(e)
        )
    except APICommunicationException as e:
        logger.error(f"Erro de comunicação na API para {ai_config.ai_client.api_client_class}: {str(e)}")
        raise
    except Exception as e:
        logger.exception(f"Erro não esperado ao processar {ai_config.ai_client.api_client_class} - Aluno: {student_id}")
        return APPResponse(
            model_name=ai_config.ai_client.api_client_class,
            configurations={},
            processing_time=0.0,
            error=f"Erro interno: {str(e)}"
        )

def process_request_data(data: JSONDict) -> JSONDict:
    logger.debug("Iniciando processamento de dados da requisição")
    
    def process_file_content(obj: any) -> None:
        if isinstance(obj, dict):
            if "type" in obj and obj["type"] == "file" and "content" in obj:
                logger.debug(f"Arquivo detectado: {obj.get('name', 'sem nome')}")
                file_text = extract_text(obj)
                obj["type"] = "text"
                obj["content"] = file_text
                if "name" in obj:
                    obj["filename"] = obj.pop("name")
            else:
                for key, value in obj.items():
                    process_file_content(value)
        elif isinstance(obj, list):
            for item in obj:
                process_file_content(item)
                
    try:
        processed = data.copy()
        process_file_content(processed)
        return processed
    except FileProcessingException:
        raise
    except Exception as e:
        logger.error(f"Erro não esperado ao processar dados: {str(e)}", exc_info=True)
        raise APIClientException(f"Erro ao processar dados da requisição: {str(e)}")
    
def process_comparison(
    user_token,
    compare_data,
    progress_callback=None,
    callback_on_complete=None
):
    """
    Processa uma comparação usando múltiplas IAs.
    
    Args:
        user_token: Token do usuário autenticado
        compare_data: Dados de comparação validados (ComparisonRequestData)
        progress_callback: Função opcional para reportar o progresso do processamento
        callback_on_complete: Função opcional chamada após completar o processamento
        
    Returns:
        ComparisonDict: Resultados das comparações por cada IA para cada aluno
    """
    logger.info(f"Iniciando processamento de comparação para {len(compare_data.students)} alunos")
    
    # Obtém configurações de IA
    user_ai_configs = AIClientTokenConfig.objects.filter(
        token=user_token,
        enabled=True
    ).select_related('ai_config', 'ai_config__ai_client')
    
    if not user_ai_configs.exists():
        logger.warning(f"Sem configurações de IA ativas para o token: {user_token}")
        raise APIClientException("Sem configurações de IA ativas para este token", status_code=400)

    # Prepara a resposta estruturada
    response_data = ComparisonDict()
    results_lock = threading.Lock()

    for student_id in compare_data.students.keys():
        # Inicializa o dicionário de respostas para cada aluno
        response_data.put_item(student_id, AIResponseDict())
          
    def store_result(config_data, student_id, result):
        """Armazena o resultado de uma comparação no dicionário de respostas."""
        with results_lock:
            client_name = config_data.ai_client.api_client_class
            response_data[student_id].put_item(client_name, result)
            
            # Calcula e notifica o progresso quando apropriado
            if progress_callback:
                completed_tasks = sum(len(resp) for resp in response_data.values())
                total_tasks = len(compare_data.students) * user_ai_configs.count()
                progress_percent = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
                progress_callback(progress_percent)

    # Agrupa configurações por Provedor de IA
    configs_by_global = {}
    for config in user_ai_configs:
        global_id = config.ai_config.ai_client.id
        if global_id not in configs_by_global:
            configs_by_global[global_id] = []
        configs_by_global[global_id].append(config.ai_config)
    
    # Configura gerenciador de tarefas
    manager = TaskManager()
    logger.debug("TaskManager inicializado")
    
    # Calcula totais para monitoramento de progresso
    total_students = len(compare_data.students)
    total_configs = user_ai_configs.count() 
    total_tasks = total_students * total_configs
    
    # Notifica progresso inicial
    if progress_callback:
        progress_callback(0.0)
    
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
                single_data = SingleComparisonRequestData(
                    instructor=compare_data.instructor,
                    student_id=student_id,
                    student=student_data
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
    
    # Monitoramento periódico de progresso durante o processamento
    if progress_callback:
        def monitor_progress():
            # Thread para monitorar o progresso enquanto o processamento ocorre
            while manager.is_processing():
                completed = sum(queue.stats.completed_tasks for queue in manager.queues)
                progress = (completed / total_tasks) * 100 if total_tasks > 0 else 0
                progress_callback(progress)
                time.sleep(0.5)  # Atualiza a cada meio segundo
                
        progress_thread = threading.Thread(target=monitor_progress)
        progress_thread.daemon = True
        progress_thread.start()
    
    # Executa o processamento
    manager.run()
    elapsed = time.time() - start_time
    
    # Atualiza o progresso final
    if progress_callback:
        progress_callback(100.0)
    
    logger.info(
        f"Processamento paralelo concluído em {elapsed:.2f}s - "
        f"{len(compare_data.students)} alunos com {user_ai_configs.count()} IAs"
    )
    
    if callback_on_complete:
        callback_on_complete(response_data)
        
    return response_data

def create_comparison_job(compare_data: ComparisonRequestData, user_token: UserToken) -> ComparisonJob:
    """
    Cria um job de comparação como uma operação de longa duração.
    
    Args:
        user_token: Token do usuário autenticado
        compare_data: Dados de comparação validados
        
    Returns:
        ComparisonJob: O job de comparação registrado
    """
    # Criar um novo job de comparação
    job = ComparisonJob(
        user_id=user_token.user.id,
        user_token_id=user_token.key,
        operation_id=str(uuid.uuid4())
    )
    
    # Adicionar os dados de entrada ao job
    job.meta = {
        "student_count": len(compare_data.students),
        "input_timestamp": time.time()
    }
    
    logger.info(f"Job de comparação registrado com ID: {job.operation_id}, {len(compare_data.students)} alunos")
    
    return job

def create_async_task(compare_data: ComparisonRequestData, user_token: UserToken) -> ComparisonTask:
    """
    Cria uma tarefa assíncrona para um job de comparação.
    
    Args:
        compare_data: Dados de comparação validados
        user_token: Token do usuário autenticado
        
    Returns:
        AsyncComparisonTask: A tarefa assíncrona criada
    """
    
    return AsyncComparisonTask(
            input_data=compare_data,
            user_id=user_token.user.id,
            token_key=user_token.key,
        )

def setup_comparison_callbacks(job, task, operation_id):
    """
    Configura callbacks para monitoramento de progresso e conclusão de comparação.
    
    Args:
        job: Job de comparação
        task: Tarefa principal do job 
        operation_id: ID da operação para logs
        
    Returns:
        tuple: (update_progress_callback, on_complete_callback)
    """
    # Função para atualizar o progresso do job
    def update_job_progress(progress: float):
        try:
            task.progress = progress
            # Atualizamos o status apenas se for a primeira atualização
            if task.status != EntityStatus.PROCESSING:
                job.update_status(EntityStatus.PROCESSING)
            # Salva o estado atualizado no banco
            Operation.from_operation_data(job)
        except Exception as e:
            logger.error(f"Erro ao atualizar progresso do job {operation_id}: {str(e)}")
    
    # Função para atualizar o resultado final
    def on_complete(response_data):
        job.update_status(EntityStatus.COMPLETED)
        task.set_result(response_data)
        # Salva o job completo no banco
        Operation.from_operation_data(job)
        logger.info(f"Job {operation_id} concluído com sucesso")
        
    return update_job_progress, on_complete

def execute_comparison(job: ComparisonJob) -> ComparisonJob:
    """
    Executa o processamento de todas as tarefas de comparação em um job.
    
    Esta função pode ser usada tanto para processamento síncrono quanto assíncrono.
    
    Args:
        job: Job de comparação contendo todas as tarefas a serem processadas
        
    Returns:
        O job atualizado com os resultados das comparações
    """
    logger.info(f"Processando job de comparação {job.operation_id} com {len(job.tasks._items)} tarefas")
    
    # Recupera o token do usuário
    try:
        user_token = UserToken.objects.get(key=job.user_token_id)
    except UserToken.DoesNotExist:
        error_msg = f"Token de usuário não encontrado: {job.user_token_id}"
        logger.error(f"[JOB:{job.operation_id}] {error_msg}")
        job.set_failure(error_msg)
        return job
    
    
    # Processar cada tarefa de comparação no job
    for task_id, task in list(job.tasks._items.items()):
        if not isinstance(task, AsyncTask):
            logger.warning(f"Tarefa {task_id} não é uma AsyncComparisonTask, ignorando")
            continue
            
        if task.status in [EntityStatus.COMPLETED, EntityStatus.FAILED]:
            logger.info(f"Tarefa {task_id} já foi processada (status: {task.status}), ignorando")
            continue
            
        # Atualiza o status da tarefa para processando
        task.update_status(EntityStatus.PROCESSING)
        task.progress = 0
        Operation.from_operation_data(job)
            
        try:
            # Extrair os dados de comparação
            if not task.input_data:
                raise ValueError(f"Dados de entrada ausentes na tarefa {task_id}")
                
            compare_data = task.input_data
            
            # Configurar callbacks para atualizar progresso e resultado
            def update_task_progress(progress: float, task_ref=task, job_ref=job):
                try:
                    task_ref.progress = progress
                    Operation.from_operation_data(job_ref)
                except Exception as e:
                    logger.error(f"Erro ao atualizar progresso da tarefa {task_ref.task_id}: {str(e)}")
            
            def on_task_complete(response_data, task_ref=task, job_ref=job):
                task_ref.set_result(response_data)
                Operation.from_operation_data(job_ref)
                logger.info(f"Tarefa {task_ref.task_id} concluída com sucesso")
            
            # Executa o processamento da comparação
            logger.info(f"Processando tarefa {task_id} - Alunos: {len(compare_data.students)}")
            result = process_comparison(
                user_token, 
                compare_data,
                progress_callback=update_task_progress,
                callback_on_complete=on_task_complete
            )
                
        except Exception as e:
            error_msg = f"Erro ao processar tarefa {task_id}: {str(e)}"
            logger.exception(error_msg)
            task.set_failure(error_msg)
            Operation.from_operation_data(job)
    
    return job

def compare_data(data, token_key: str, sync: bool = True) -> OperationData:
    """
    Processa dados de comparação de forma síncrona ou assíncrona.
    
    Args:
        data: Dados da requisição de comparação
        token_key: Token do usuário autenticado
        sync: Se True, executa processamento síncrono; se False, cria job assíncrono
        
    Returns:
        OperationData: Job de comparação (com resultado se síncrono)
    """
    # Busca o token do usuário
    user_token = UserToken.objects.get(key=token_key)
    logger.debug(f"Token validado para usuário: {user_token.user.username}")
    
    # Processa os dados da requisição
    processed_data = process_request_data(data)
    compare_data = ComparisonRequestData(
        instructor=processed_data.get('instructor', {}),
        students=processed_data.get('students', {})
    )
    
    # Criar e registrar um job de comparação 
    job = create_comparison_job(compare_data, user_token)
    task = create_async_task(compare_data, user_token)
    job.tasks.put_item(task)

    Operation.from_operation_data(job)
    
    if sync:
        # Para operações síncronas, processamos imediatamente
        logger.info(f"Processando job síncrono {job.operation_id} para usuário {user_token.user.username}")
        
        # Executa o processamento 
        return execute_comparison(job)
    else:
        # Para assíncrono, enviamos para o Celery
        process_comparison_job.delay(job.operation_id)
    
        logger.info(f"Operação assíncrona {job.operation_id} registrada para usuário {user_token.user.username}")
        
        return job

