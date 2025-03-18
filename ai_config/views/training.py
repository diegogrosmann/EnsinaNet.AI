"""
Views para gerenciamento de treinamentos de modelos de IA.

Este módulo contém funções para exibir o painel de treinamento,
iniciar novos treinamentos, monitorar o progresso de treinamentos ativos,
cancelar treinamentos em andamento e excluir registros de treinamento.
"""

import logging
import json
import base64
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.db import transaction
from typing import Dict, List, Any

from ai_config.models import (
    AIClientConfiguration,
    AITraining,
    AITrainingFile,
    TrainingCapture
)
from ai_config.forms import (
    TrainingCaptureForm,
)

from core.types import (
    AITrainingStatus, 
    AITrainingResponse,
    APPResponse
)
from core.types.training import AITrainingFileDataCollection

logger = logging.getLogger(__name__)

@login_required 
def training_center(request: HttpRequest) -> HttpResponse:
    """Renderiza a página do Training Center com os arquivos disponíveis.
    
    Apresenta a interface principal do centro de treinamento, mostrando
    arquivos de treinamento, IAs disponíveis para treinamento e captura ativa.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        HttpResponse: Página do centro de treinamento renderizada.
    """
    user = request.user
    logger.debug(f"Acessando Training Center para usuário: {user.email}")
    
    try:
        # Obtém todos os arquivos de treinamento do usuário
        training_files_db = AITrainingFile.objects.filter(user=user)
        
        # Converte para coleção tipada AITrainingFileDataCollection
        training_files: AITrainingFileDataCollection = []
        for file in training_files_db:
            try:
                training_files.append(file.to_data())
            except Exception as e:
                logger.warning(f"Erro ao converter arquivo de treinamento {file.id} para formato de dados: {e}")
                continue
            
        logger.debug(f"Encontrados {len(training_files)} arquivos de treinamento para {user.email}")
        
        # Obtém todas as configurações de IA do usuário
        all_ais = AIClientConfiguration.objects.filter(
            user=user
        ).select_related('user', 'ai_client')
        
        # Filtra apenas as IAs que suportam treinamento
        trainable_ais = []
        for ai_config in all_ais:
            try:
                client = ai_config.create_api_client_instance()
                if client.can_train:
                    trainable_ais.append({
                        'config': ai_config
                    })
            except Exception as e:
                logger.warning(f"Erro ao verificar capacidade de treinamento para {ai_config.name} (ID: {ai_config.id}): {e}")
                continue
        
        logger.debug(f"Encontradas {len(trainable_ais)} IAs treináveis para {user.email}")
        
        # Obter lista única de tipos de API Client disponíveis
        api_client_types = set()
        for ai in trainable_ais:
            api_client_types.add(ai['config'].ai_client.api_client_class)
        
        # Obtém a captura ativa (se houver)
        active_capture = TrainingCapture.objects.filter(token__user=user, is_active=True).first()
        if active_capture:
            logger.debug(f"Captura ativa encontrada para {user.email}: token={active_capture.token.name}, AI={active_capture.ai_client_config.name}")
        
        if request.method == 'POST':
            form = TrainingCaptureForm(request.POST, user=user)
            if form.is_valid():
                # Redirecionar para create_training_file em vez de treinamento_ia
                logger.info(f"Formulário de captura enviado por {user.email}, redirecionando para criação de arquivo")
                return redirect('ai_config:create_training_file')
            else:
                logger.warning(f"Formulário de captura inválido: {form.errors}")
        else:
            form = TrainingCaptureForm(user=user)
        
        context = {
            'training_files': training_files,
            'trainable_ais': trainable_ais,
            'api_client_types': sorted(api_client_types),  # Ordenar para exibição
            'active_capture': active_capture,
            'form': TrainingCaptureForm(user=user) if not active_capture else None,
            'capture_form': TrainingCaptureForm(user=user),
        }
        
        return render(request, 'training/center.html', context)
    except Exception as e:
        logger.exception(f"Erro ao carregar Training Center para {user.email}: {e}")
        messages.error(request, f'Ocorreu um erro ao carregar o Training Center: {str(e)}')
        # Retornar uma página com mensagem de erro, mas sem contexto completo
        return render(request, 'training/center.html', {'error': True})

@login_required
def training_ai(request: HttpRequest) -> JsonResponse:
    """Realiza o treinamento das IAs selecionadas.
    
    Inicia processo de treinamento para IAs selecionadas usando o
    arquivo de treinamento especificado. Processa as respostas e 
    notifica o usuário sobre sucessos e falhas.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        JsonResponse: Resposta JSON com status da operação.
    """
    if request.method != 'POST':
        response = APPResponse(
            success=False,
            error='Método não permitido'
        )
        return JsonResponse(response.to_dict(), status=405)
        
    # Verificar se a requisição é AJAX
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response = APPResponse(
            success=False,
            error='Apenas requisições AJAX são permitidas'
        )
        return JsonResponse(response.to_dict(), status=400)

    try:
        user = request.user
        logger.debug(f"Solicitação de treinamento de IA recebida de {user.email}")
        logger.debug(f"Dados da solicitação: {request.POST}")
        
        # Validar seleção de IAs
        selected_ais = request.POST.getlist('selected_ais', [])
        if not selected_ais:
            response = APPResponse(
                success=False,
                error='Nenhuma IA selecionada'
            )
            return JsonResponse(response.to_dict(), status=400)

        # Validar arquivo de treinamento
        file_id = request.POST.get('file_id')
        if not file_id:
            logger.warning(f"Tentativa de treinamento sem especificar arquivo por {user.email}")
            response = APPResponse(
                success=False,
                error='Arquivo de treinamento não especificado'
            )
            return JsonResponse(response.to_dict(), status=400)

        # Verificar existência do arquivo e propriedade
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        
        # Obter dados estruturados do arquivo
        training_file_data = training_file.to_data()
        
        logger.info(f"Iniciando treinamento com arquivo '{training_file.name}' (ID: {file_id}) para {len(selected_ais)} IAs")

        # Verificar se todas as IAs selecionadas pertencem ao usuário
        ai_count = AIClientConfiguration.objects.filter(
            id__in=selected_ais, 
            user=user
        ).count()
        
        if ai_count != len(selected_ais):
            logger.warning(f"Tentativa de treinar IAs que não pertencem ao usuário {user.email}")
            response = APPResponse(
                success=False,
                error='Algumas IAs selecionadas não pertencem ao seu usuário'
            )
            return JsonResponse(response.to_dict(), status=403)

        # Inicia o treinamento para cada IA selecionada
        results = []
        successful_trainings = []
        failed_trainings = []

        for ai_id in selected_ais:
            try:
                ai_config = AIClientConfiguration.objects.get(id=ai_id)
                logger.debug(f"Iniciando treinamento para IA '{ai_config.name}' (ID: {ai_id})")
                
                with transaction.atomic():
                    # Criar cliente API
                    client = ai_config.create_api_client_instance()
                    
                    # Verificar se suporta treinamento
                    if not getattr(client, 'can_train', False):
                        error_msg = "Esta IA não suporta treinamento"
                        logger.warning(f"{error_msg}: {ai_config.name} (ID: {ai_id})")
                        failed_trainings.append({
                            'ai_name': ai_config.name,
                            'error': error_msg,
                            'status': AITrainingStatus.FAILED.value
                        })
                        continue
                    
                    # Iniciar treinamento
                    training_response = client.train(training_file_data)
                    
                    # Criar registro de treinamento
                    training = AITraining.objects.create(
                        ai_config=ai_config,
                        file=training_file,
                        job_id=training_response.job_id,
                        status=training_response.status.value,
                        progress=training_response.progress
                    )
                    
                    result = {
                        'ai_name': ai_config.name,
                        'job_id': training_response.job_id, 
                        'status': training_response.status.value,
                        'training_id': training.id
                    }
                    
                    results.append(result)
                    
                    if training_response.status == AITrainingStatus.IN_PROGRESS:
                        successful_trainings.append(result)
                        logger.info(f"Treinamento iniciado com sucesso para IA '{ai_config.name}' (ID: {ai_id})")
                    else:
                        failed_trainings.append({
                            **result,
                            'error': training_response.error or "Erro desconhecido"
                        })
                        error_msg = training_response.error or "Erro desconhecido"
                        logger.warning(f"Falha ao iniciar treinamento para IA '{ai_config.name}' (ID: {ai_id}): {error_msg}")
            except Exception as e:
                logger.exception(f"Erro ao iniciar treinamento para IA {ai_id}: {e}")
                failed_trainings.append({
                    'ai_name': getattr(ai_config, 'name', f'IA {ai_id}'),
                    'error': str(e),
                    'status': AITrainingStatus.FAILED.value
                })

        # Preparar mensagens para retorno AJAX (não usar messages do Django)
        success_msg = None
        fail_msg = None
        
        if successful_trainings:
            success_msg = f'Treinamento iniciado com sucesso para {len(successful_trainings)} IAs: '
            success_msg += ', '.join(t.get('ai_name', 'IA') for t in successful_trainings)
            
        if failed_trainings:
            fail_msg = f'Falha ao iniciar treinamento para {len(failed_trainings)} IAs: '
            fail_details = []
            for fail in failed_trainings:
                fail_details.append(f"{fail.get('ai_name', 'IA')}: {fail.get('error', 'Erro desconhecido')}")
            fail_msg += '; '.join(fail_details)

        if not successful_trainings and failed_trainings:
            response = APPResponse(
                success=False,
                error=fail_msg
            )
            return JsonResponse(response.to_dict(), status=500)

        response = APPResponse(
            success=bool(successful_trainings),
            data={
                'successful': successful_trainings,
                'failed': failed_trainings,
                'success_message': success_msg,
                'error_message': fail_msg
            }
        )
        return JsonResponse(response.to_dict())

    except AITrainingFile.DoesNotExist:
        logger.warning(f"Tentativa de treinamento com arquivo inexistente: {file_id}")
        response = APPResponse(
            success=False,
            error='Arquivo de treinamento não encontrado'
        )
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        response = APPResponse(
            success=False,
            error=str(e)
        )
        return JsonResponse(response.to_dict(), status=500)

@login_required
def training_monitor(request: HttpRequest) -> JsonResponse:
    """Endpoint unificado para monitoramento de treinamento.
    
    Se fornecidos job_ids[] e config_ids[], retorna o status específico desses treinamentos.
    Caso contrário, retorna o status geral de todos os treinamentos.
    
    Args:
        request: Objeto de requisição HTTP com parâmetros opcionais job_ids[] e config_ids[]
        
    Returns:
        JsonResponse: Informações atualizadas sobre os treinamentos solicitados
    """
    user = request.user
    logger.debug(f"Monitoramento de treinamento solicitado por {user.email}")
    
    # Verifica se há parâmetros específicos de job para um monitoramento detalhado
    job_ids = request.GET.getlist('job_ids[]')
    config_ids = request.GET.getlist('config_ids[]')
    
    if job_ids and config_ids and len(job_ids) == len(config_ids):
        # Monitoramento detalhado de jobs específicos
        results: List[Dict[str, Any]] = []
        try:
            logger.debug(f"Monitorando {len(job_ids)} jobs específicos")
            
            for job_id, config_id in zip(job_ids, config_ids):
                try:
                    # Verificar se a configuração pertence ao usuário
                    config = AIClientConfiguration.objects.get(
                        id=config_id,
                        user=user
                    )
                    
                    try:
                        client = config.create_api_client_instance()
                        if not getattr(client, 'can_train', False):
                            logger.warning(f"IA '{config.name}' não suporta treinamento")
                            results.append({
                                'job_id': job_id,
                                'config_id': config_id,
                                'error': 'IA não suporta treinamento'
                            })
                            continue
                            
                        # Obter status tipado
                        training_response: AITrainingResponse = client.get_training_status(job_id)
                        
                        logger.debug(f"Status do job {job_id} para IA '{config.name}': {training_response.status.value}, progresso: {training_response.progress:.1%}")
                        
                        # Atualizar o registro do treinamento
                        try:
                            training = AITraining.objects.get(job_id=job_id, ai_config=config)
                            
                            # Atualizar status somente se for diferente
                            if training.status != training_response.status.value or training.progress != training_response.progress:
                                training.status = training_response.status.value
                                training.progress = training_response.progress
                                
                                if training_response.model_name:
                                    training.model_name = training_response.model_name
                                
                                if training_response.error:
                                    training.error = training_response.error
                                    
                                training.save()
                        except AITraining.DoesNotExist:
                            # Registro não encontrado, pode ter sido excluído
                            pass
                        
                        # Construir resposta
                        results.append({
                            'job_id': job_id,
                            'config_id': config_id,
                            'completed': training_response.status in [AITrainingStatus.COMPLETED, AITrainingStatus.FAILED],
                            'status': training_response.status.value,
                            'progress': round(training_response.progress * 100, 2),
                            'error': training_response.error,
                            'model_name': training_response.model_name
                        })
                    except Exception as e:
                        logger.error(f"Erro ao obter status do job {job_id} para IA {config_id}: {e}")
                        results.append({
                            'job_id': job_id,
                            'config_id': config_id,
                            'error': str(e)
                        })
                except AIClientConfiguration.DoesNotExist:
                    logger.warning(f"Configuração de IA não encontrada ou não pertence ao usuário: {config_id}")
                    results.append({
                        'job_id': job_id,
                        'config_id': config_id,
                        'error': 'Configuração não encontrada'
                    })
            
            response = APPResponse(
                success=True,
                data={'results': results}
            )
            return JsonResponse(response.to_dict())
            
        except Exception as e:
            logger.exception(f"Erro ao monitorar progresso dos treinamentos: {e}")
            response = APPResponse(
                success=False,
                error=str(e)
            )
            return JsonResponse(response.to_dict(), status=500)
    else:
        # Listagem geral de todos os treinamentos do usuário
        try:
            trainings_data: List[Dict[str, Any]] = []
            queue_status = {'queued': 0, 'started': 0, 'finished': 0}
            
            # Consulta corrigida: filtrar diretamente pelo usuário dono da configuração
            active_trainings = AITraining.objects.filter(
                ai_config__user=user
            ).select_related(
                'ai_config__ai_client',
                'file'
            ).order_by('-created_at')
            
            logger.debug(f"Encontrados {active_trainings.count()} treinamentos para o usuário {user.email}")
            
            for training in active_trainings:
                # Mapear status string para enum
                status = AITrainingStatus(training.status)
                
                # Contabilizar status para estatísticas
                if status == AITrainingStatus.NOT_STARTED:
                    queue_status['queued'] += 1
                elif status == AITrainingStatus.IN_PROGRESS:
                    queue_status['started'] += 1
                elif status in [AITrainingStatus.COMPLETED, AITrainingStatus.FAILED]:
                    queue_status['finished'] += 1
                
                # Preparar dados do treinamento para retorno
                trainings_data.append({
                    'id': str(training.id), 
                    'job_id': training.job_id, 
                    'ai_name': training.ai_config.name,
                    'file_name': training.file.name if training.file else 'N/A',
                    'status': status.value,
                    'error': training.error,
                    'model_name': training.model_name,
                    'progress': training.progress, 
                    'created_at': training.created_at.isoformat() if training.created_at else None,
                    'updated_at': training.updated_at.isoformat() if training.updated_at else None,
                })
            
            response = APPResponse(
                success=True,
                data={
                    'trainings': trainings_data,
                    'queue_status': queue_status
                }
            )
            return JsonResponse(response.to_dict())
            
        except Exception as e:
            logger.exception(f"Erro ao obter status dos treinamentos: {e}")
            response = APPResponse(
                success=False,
                error=str(e),
                data={
                    'trainings': [],
                    'queue_status': {'queued': 0, 'started': 0, 'finished': 0}
                }
            )
            return JsonResponse(response.to_dict(), status=500)

@login_required
@require_http_methods(["POST"])
def training_cancel(request: HttpRequest, training_id: int) -> JsonResponse:
    """Endpoint para cancelamento de treinamento.
    
    Cancela um treinamento em andamento, se possível.
    
    Args:
        request: Objeto de requisição HTTP.
        training_id: ID do treinamento a ser cancelado.
        
    Returns:
        JsonResponse: Status da operação de cancelamento.
    """
    if not training_id:
        logger.warning(f"Tentativa de cancelar treinamento sem fornecer ID por {request.user.email}")
        response = APPResponse(
            success=False,
            error='ID do treinamento não fornecido'
        )
        return JsonResponse(response.to_dict(), status=400)
        
    try:
        # Encontra o treinamento pelo ID numérico e verifica permissão
        training = get_object_or_404(
            AITraining, 
            id=training_id,
            ai_config__user=request.user
        )
        
        logger.info(f"Tentativa de cancelar treinamento {training_id} da IA '{training.ai_config.name}' por {request.user.email}")
        
        # Verificar se o treinamento está em andamento
        if training.status != AITrainingStatus.IN_PROGRESS.value:
            logger.warning(f"Tentativa de cancelar treinamento que não está em andamento: {training_id}")
            response = APPResponse(
                success=False,
                error='Apenas treinamentos em andamento podem ser cancelados'
            )
            return JsonResponse(response.to_dict(), status=400)
        
        # Usa o método cancel_training()
        if training.cancel_training():
            logger.info(f"Treinamento {training_id} cancelado com sucesso")
            messages.success(request, 'Treinamento cancelado com sucesso')
            
            # Atualizar o status manualmente para garantir
            training.status = AITrainingStatus.CANCELLED.value
            training.save(update_fields=['status'])
            
            response = APPResponse(
                success=True,
                data={'message': 'Treinamento cancelado com sucesso'}
            )
            return JsonResponse(response.to_dict())
        else:
            logger.warning(f"Não foi possível cancelar treinamento {training_id}")
            response = APPResponse(
                success=False,
                error='Não foi possível cancelar o treinamento. Aguarde sua finalização e exclua o modelo.'
            )
            return JsonResponse(response.to_dict(), status=400)
            
    except AITraining.DoesNotExist:
        logger.warning(f"Tentativa de cancelar treinamento inexistente: {training_id}")
        response = APPResponse(
            success=False,
            error='Treinamento não encontrado'
        )
        return JsonResponse(response.to_dict(), status=404)
    except PermissionDenied:
        logger.warning(f"Tentativa de cancelar treinamento sem permissão: {training_id}")
        response = APPResponse(
            success=False,
            error='Você não tem permissão para cancelar este treinamento'
        )
        return JsonResponse(response.to_dict(), status=403)
    except Exception as e:
        logger.exception(f"Erro ao cancelar treinamento: {e}")
        response = APPResponse(
            success=False,
            error=str(e)
        )
        return JsonResponse(response.to_dict(), status=500)

@login_required
@require_http_methods(["POST"])
def training_delete(request: HttpRequest, training_id: int) -> JsonResponse:
    if not training_id:
        logger.warning(f"Tentativa de excluir treinamento sem fornecer ID por {request.user.email}")
        response = APPResponse(
            success=False,
            error='ID do treinamento não fornecido'
        )
        return JsonResponse(response.to_dict(), status=400)
        
    try:
        training = get_object_or_404(
            AITraining, 
            id=training_id,
            ai_config__user=request.user
        )
        
        logger.info(f"Excluindo treinamento {training_id} ({training.status}) da IA '{training.ai_config.name}' por {request.user.email}")
        
        if training.status == 'in_progress':
            logger.info(f"Tentando cancelar treinamento em andamento antes da exclusão: {training_id}")
            training.cancel_training()
        
        with transaction.atomic():
            training.delete()
        
        logger.info(f"Treinamento {training_id} excluído com sucesso")
        
        response = APPResponse(
            success=True,
            data={'message': 'Treinamento excluído com sucesso'}
        )
        return JsonResponse(response.to_dict())
            
    except AITraining.DoesNotExist:
        logger.warning(f"Tentativa de excluir treinamento inexistente: {training_id}")
        response = APPResponse(
            success=False,
            error='Treinamento não encontrado'
        )
        return JsonResponse(response.to_dict(), status=404)
    except PermissionDenied:
        logger.warning(f"Tentativa de excluir treinamento sem permissão: {training_id}")
        response = APPResponse(
            success=False,
            error='Você não tem permissão para excluir este treinamento'
        )
        return JsonResponse(response.to_dict(), status=403)
    except Exception as e:
        logger.exception(f"Erro ao excluir treinamento {training_id}: {e}")
        response = APPResponse(
            success=False,
            error=str(e)
        )
        return JsonResponse(response.to_dict(), status=500)

# Substituindo a função check_client_can_train para usar tipos adequados
def check_client_can_train(ai_config: AIClientConfiguration) -> bool:
    """Verifica se um cliente de IA suporta treinamento.
    
    Args:
        ai_config: Configuração da IA a ser verificada
        
    Returns:
        bool: True se o cliente suporta treinamento, False caso contrário
    """
    try:
        # Criar cliente diretamente
        ai_client = ai_config.create_api_client_instance()
        
        # Verificar o atributo can_train
        return getattr(ai_client, "can_train", False)
    except Exception as e:
        logger.warning(f"Erro ao verificar capacidade de treinamento para {ai_config.name} (ID: {ai_config.id}): {str(e)}")
        return False