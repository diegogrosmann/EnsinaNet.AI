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

from core.validators import validate_training_file_content
from accounts.models import UserToken
from ai_config.models import (
    AIClientGlobalConfiguration,
    AIClientConfiguration,
    AITraining,
    AITrainingFile,
    TrainingCapture
)
from ai_config.forms import (
    TrainingCaptureForm,
)

from api.utils.clientsIA import AITrainingStatus

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
        training_files = AITrainingFile.objects.filter(user=user)
        
        # Remove registros de arquivos que não existem mais fisicamente
        files_removed = 0
        for training_file in training_files:
            if not training_file.file_exists():
                logger.warning(f"Removendo registro de arquivo físico inexistente: '{training_file.name}' (ID: {training_file.id})")
                training_file.delete()
                files_removed += 1
        
        if files_removed > 0:
            logger.info(f"Removidos {files_removed} registros de arquivos físicos inexistentes para {user.email}")
        
        # Recarrega a lista após a limpeza
        training_files = AITrainingFile.objects.filter(user=user).order_by('-uploaded_at')
        logger.debug(f"Encontrados {training_files.count()} arquivos de treinamento para {user.email}")
        
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
        logger.warning(f"Tentativa de iniciar treinamento com método não permitido: {request.method}")
        messages.error(request, 'Método não permitido')
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        user = request.user
        logger.debug(f"Solicitação de treinamento de IA recebida de {user.email}")
        logger.debug(f"Dados da solicitação: {request.POST}")
        
        # Validar seleção de IAs
        selected_ais = request.POST.getlist('selected_ais', [])
        if not selected_ais:
            logger.warning(f"Tentativa de treinamento sem selecionar IAs por {user.email}")
            messages.warning(request, 'Nenhuma IA selecionada')
            return JsonResponse({'error': 'Nenhuma IA selecionada'}, status=400)

        # Validar arquivo de treinamento
        file_id = request.POST.get('file_id')
        if not file_id:
            logger.warning(f"Tentativa de treinamento sem especificar arquivo por {user.email}")
            messages.warning(request, 'Arquivo de treinamento não especificado')
            return JsonResponse({'error': 'Arquivo de treinamento não especificado'}, status=400)

        # Verificar existência do arquivo e propriedade
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        logger.info(f"Iniciando treinamento com arquivo '{training_file.name}' (ID: {file_id}) para {len(selected_ais)} IAs")

        # Verificar se todas as IAs selecionadas pertencem ao usuário
        ai_count = AIClientConfiguration.objects.filter(
            id__in=selected_ais, 
            user=user
        ).count()
        
        if ai_count != len(selected_ais):
            logger.warning(f"Tentativa de treinar IAs que não pertencem ao usuário {user.email}")
            messages.error(request, 'Algumas IAs selecionadas não pertencem ao seu usuário')
            return JsonResponse({'error': 'Permissão negada'}, status=403)

        # Inicia o treinamento para cada IA selecionada
        results = []
        successful_trainings = []
        failed_trainings = []

        for ai_id in selected_ais:
            try:
                ai_config = AIClientConfiguration.objects.get(id=ai_id)
                logger.debug(f"Iniciando treinamento para IA '{ai_config.name}' (ID: {ai_id})")
                
                with transaction.atomic():
                    result = ai_config.perform_training(training_file)
                
                results.append(result)
                if result.get('status') == AITrainingStatus.IN_PROGRESS:
                    successful_trainings.append(result)
                    logger.info(f"Treinamento iniciado com sucesso para IA '{ai_config.name}' (ID: {ai_id})")
                else:
                    failed_trainings.append(result)
                    error_msg = result.get('error', 'Erro desconhecido')
                    logger.warning(f"Falha ao iniciar treinamento para IA '{ai_config.name}' (ID: {ai_id}): {error_msg}")
            except Exception as e:
                logger.exception(f"Erro ao iniciar treinamento para IA {ai_id}: {e}")
                failed_trainings.append({
                    'ai_name': getattr(ai_config, 'name', f'IA {ai_id}'),
                    'error': str(e),
                    'status': AITrainingStatus.FAILED
                })

        # Monta as mensagens detalhadas
        if successful_trainings:
            success_msg = f'Treinamento iniciado com sucesso para {len(successful_trainings)} IAs: '
            success_msg += ', '.join(t.get('ai_name', 'IA') for t in successful_trainings)
            messages.success(request, success_msg)
            
        if failed_trainings:
            fail_msg = f'Falha ao iniciar treinamento para {len(failed_trainings)} IAs:\n'
            for fail in failed_trainings:
                fail_msg += f"\n- {fail.get('ai_name', 'IA')}: {fail.get('error', 'Erro desconhecido')}"
            messages.error(request, fail_msg)

        if not successful_trainings and failed_trainings:
            logger.error(f"Nenhum treinamento iniciado com sucesso para o usuário {user.email}")
            return JsonResponse({'success': False, 'error': 'Falha ao iniciar todos os treinamentos solicitados'}, status=500)

        return JsonResponse({'success': bool(successful_trainings)})

    except AITrainingFile.DoesNotExist:
        logger.warning(f"Tentativa de treinamento com arquivo inexistente: {file_id}")
        messages.error(request, 'Arquivo de treinamento não encontrado')
        return JsonResponse({'success': False, 'error': 'Arquivo não encontrado'}, status=404)
    except Exception as e:
        logger.exception(f"Erro não tratado durante o processamento de treinamento: {e}")
        messages.error(request, f'Erro durante o treinamento: {str(e)}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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
        # Lógica da antiga função training_progress
        results = []
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
                        if not client.can_train:
                            logger.warning(f"IA '{config.name}' não suporta treinamento")
                            results.append({
                                'job_id': job_id,
                                'config_id': config_id,
                                'error': 'IA não suporta treinamento'
                            })
                            continue
                            
                        status = client.get_training_status(job_id)
                        logger.debug(f"Status do job {job_id} para IA '{config.name}': {status.status.value}, progresso: {status.progress:.1%}")
                        
                        results.append({
                            'job_id': job_id,
                            'config_id': config_id,
                            'completed': status.status in [AITrainingStatus.COMPLETED, AITrainingStatus.FAILED],
                            'status': status.status.value,
                            'progress': round(status.progress * 100, 2),
                            'error': status.error if status.error else None,
                            'model_name': status.model_name if status.model_name else None
                        })
                    except Exception as e:
                        logger.error(f"Erro ao obter status do job {job_id} para IA {config_id}: {e}")
                        results.append({
                            'job_id': job_id,
                            'config_id': config_id,
                            'error': str(e)
                        })
                        continue
                except AIClientConfiguration.DoesNotExist:
                    logger.warning(f"Configuração de IA não encontrada ou não pertence ao usuário: {config_id}")
                    results.append({
                        'job_id': job_id,
                        'config_id': config_id,
                        'error': 'Configuração não encontrada'
                    })
                    continue
                
            return JsonResponse({'results': results})
            
        except Exception as e:
            logger.exception(f"Erro ao monitorar progresso dos treinamentos: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        # Lógica da antiga função training_status - listagem geral
        try:
            trainings = []
            queue_status = {'queued': 0, 'started': 0, 'finished': 0}
            
            # Consulta corrigida: filtrar diretamente pelo usuário dono da configuração
            active_trainings = AITraining.objects.filter(
                ai_config__user=user  # Filtro direto pelo usuário da configuração
            ).select_related(
                'ai_config__ai_client',
                'file'
            ).order_by('-created_at')
            
            logger.debug(f"Encontrados {active_trainings.count()} treinamentos para o usuário {user.email}")
            
            for training in active_trainings:
                if training.status == 'not_started':
                    queue_status['queued'] += 1
                elif training.status == 'in_progress':
                    queue_status['started'] += 1
                elif training.status in ['completed', 'failed']:
                    queue_status['finished'] += 1
                
                trainings.append({
                    'id': str(training.id), 
                    'job_id': training.job_id, 
                    'ai_name': training.ai_config.name,
                    'file_name': training.file.name if training.file else 'N/A',
                    'status': training.status,
                    'error': training.error,
                    'model_name': training.model_name,
                    'progress': training.progress, 
                    'completed_at': training.created_at.isoformat() if training.created_at else None 
                })
            
            return JsonResponse({
                'success': True,
                'trainings': trainings,
                'queue_status': queue_status
            })
            
        except Exception as e:
            logger.exception(f"Erro ao obter status geral dos treinamentos para {user.email}: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e),
                'trainings': [],
                'queue_status': {'queued': 0, 'started': 0, 'finished': 0}
            }, status=500)

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
        messages.error(request, 'ID do treinamento não fornecido')
        return JsonResponse({'success': False}, status=400)
        
    try:
        # Encontra o treinamento pelo ID numérico e verifica permissão
        training = get_object_or_404(
            AITraining, 
            id=training_id,
            ai_config__user=request.user
        )
        
        logger.info(f"Tentativa de cancelar treinamento {training_id} da IA '{training.ai_config.name}' por {request.user.email}")
        
        # Usa o método cancel_training()
        if training.cancel_training():
            logger.info(f"Treinamento {training_id} cancelado com sucesso")
            messages.success(request, 'Treinamento cancelado com sucesso')
            return JsonResponse({'success': True})
        else:
            logger.warning(f"Não foi possível cancelar treinamento {training_id} - status atual: {training.status}")
            messages.error(request, 'Não foi possível cancelar o treinamento. \nAguarde sua finalização e exclua o modelo.')
            return JsonResponse({'success': False}, status=400)
            
    except AITraining.DoesNotExist:
        logger.warning(f"Tentativa de cancelar treinamento inexistente: {training_id}")
        messages.error(request, 'Treinamento não encontrado')
        return JsonResponse({'success': False}, status=404)
    except PermissionDenied:
        logger.warning(f"Tentativa de cancelar treinamento sem permissão: {training_id}")
        messages.error(request, 'Você não tem permissão para cancelar este treinamento')
        return JsonResponse({'success': False}, status=403)
    except Exception as e:
        logger.exception(f"Erro ao cancelar treinamento {training_id}: {e}")
        messages.error(request, f'Erro ao cancelar treinamento: {str(e)}')
        return JsonResponse({'success': False}, status=500)

@login_required
@require_http_methods(["POST"])
def training_delete(request: HttpRequest, training_id: int) -> JsonResponse:
    """Endpoint para excluir um treinamento.
    
    Remove um registro de treinamento do sistema. 
    Se o treinamento estiver em andamento, tentará cancelá-lo primeiro.
    
    Args:
        request: Objeto de requisição HTTP.
        training_id: ID do treinamento a ser excluído.
        
    Returns:
        JsonResponse: Status da operação de exclusão.
    """
    if not training_id:
        logger.warning(f"Tentativa de excluir treinamento sem fornecer ID por {request.user.email}")
        messages.error(request, 'ID do treinamento não fornecido')
        return JsonResponse({'error': 'ID do treinamento não fornecido'}, status=400)
        
    try:
        # Encontra o treinamento pelo ID numérico e verifica permissão
        training = get_object_or_404(
            AITraining, 
            id=training_id,
            ai_config__user=request.user
        )
        
        logger.info(f"Excluindo treinamento {training_id} ({training.status}) da IA '{training.ai_config.name}' por {request.user.email}")
        
        # Se estiver em andamento, tenta cancelar primeiro
        if training.status == 'in_progress':
            logger.info(f"Tentando cancelar treinamento em andamento antes da exclusão: {training_id}")
            training.cancel_training()
        
        # Remove o registro em uma transação
        with transaction.atomic():
            training.delete()
        
        logger.info(f"Treinamento {training_id} excluído com sucesso")
        messages.success(request, 'Treinamento excluído com sucesso')
        return JsonResponse({'message': 'Treinamento excluído com sucesso'})
            
    except AITraining.DoesNotExist:
        logger.warning(f"Tentativa de excluir treinamento inexistente: {training_id}")
        messages.error(request, 'Treinamento não encontrado')
        return JsonResponse({'error': 'Treinamento não encontrado'}, status=404)
    except PermissionDenied:
        logger.warning(f"Tentativa de excluir treinamento sem permissão: {training_id}")
        messages.error(request, 'Você não tem permissão para excluir este treinamento')
        return JsonResponse({'error': 'Permissão negada'}, status=403)
    except Exception as e:
        logger.exception(f"Erro ao excluir treinamento {training_id}: {e}")
        messages.error(request, f'Erro ao excluir treinamento: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

# Alterar o código que causa o warning
def check_client_can_train(ai_config):
    """Verifica se um cliente de IA suporta treinamento."""
    try:
        # Acessar o atributo diretamente em vez de usar o método get()
        client_config = ai_config.to_dict()  # AIConfigData já é retornado como dicionário
        
        # Criar cliente e verificar se suporta treinamento
        ai_client = ai_config.create_api_client_instance()
        return ai_client.can_train if hasattr(ai_client, "can_train") else False
    except Exception as e:
        logger.warning(f"Erro ao verificar capacidade de treinamento para {ai_config.name} (ID: {ai_config.id}): {str(e)}")
        return False