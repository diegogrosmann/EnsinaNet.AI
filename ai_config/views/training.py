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

from api.utils.clientsIA import TrainingStatus

logger = logging.getLogger(__name__)

@login_required 
def training_center(request: HttpRequest) -> HttpResponse:
    """Renderiza a página do Training Center com os arquivos disponíveis."""
    user = request.user
    
    # Obtém todos os arquivos de treinamento do usuário
    training_files = AITrainingFile.objects.filter(user=user)
    
    # Remove registros de arquivos que não existem mais fisicamente
    for training_file in training_files:
        if not training_file.file_exists():
            training_file.delete()
    
    # Recarrega a lista após a limpeza
    training_files = AITrainingFile.objects.filter(user=user).order_by('-uploaded_at')
    
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
            logger.warning(f"Erro ao verificar treinamento para {ai_config}: {e}")
            continue
    
    # Obter lista única de tipos de API Client disponíveis
    api_client_types = set()
    for ai in trainable_ais:
        api_client_types.add(ai['config'].ai_client.api_client_class)
    
    # Obtém a captura ativa (se houver)
    active_capture = TrainingCapture.objects.filter(token__user=user, is_active=True).first()
    
    if request.method == 'POST':
        form = TrainingCaptureForm(request.POST, user=user)
        if form.is_valid():
            # Redirecionar para create_training_file em vez de treinamento_ia
            return redirect('ai_config:create_training_file')
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

@login_required
def training_ai(request: HttpRequest) -> HttpResponse:
    """Realiza o treinamento das IAs selecionadas."""
    if request.method != 'POST':
        messages.error(request, 'Método não permitido')
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        logger.debug(f"POST data: {request.POST}")
        logger.debug(f"Selected IAs: {request.POST.getlist('selected_ais')}")
        
        selected_ais = request.POST.getlist('selected_ais', [])
        if not selected_ais:
            messages.warning(request, 'Nenhuma IA selecionada')
            return JsonResponse({'error': 'Nenhuma IA selecionada'}, status=400)

        file_id = request.POST.get('file_id')
        if not file_id:
            messages.warning(request, 'Arquivo de treinamento não especificado')
            return JsonResponse({'error': 'Arquivo de treinamento não especificado'}, status=400)

        training_file = get_object_or_404(AITrainingFile, id=file_id, user=request.user)

        if not AIClientConfiguration.objects.filter(
            id__in=selected_ais, 
            user=request.user
        ).count() == len(selected_ais):
            messages.error(request, 'Algumas IAs selecionadas não pertencem ao seu usuário')
            return JsonResponse({'error': 'Permissão negada'}, status=403)

        # Inicia o treinamento para cada IA selecionada
        results = []
        successful_trainings = []
        failed_trainings = []

        for ai_id in selected_ais:
            ai_config = AIClientConfiguration.objects.get(id=ai_id)
            try:
                result = ai_config.perform_training(training_file)
                results.append(result)
                if result['status'] == TrainingStatus.IN_PROGRESS:
                    successful_trainings.append(result)
                else:
                    failed_trainings.append(result)
            except Exception as e:
                failed_trainings.append({
                    'ai_name': ai_config.name,
                    'error': str(e),
                    'status': TrainingStatus.FAILED
                })

        # Monta as mensagens detalhadas
        if successful_trainings:
            success_msg = f'Treinamento iniciado com sucesso para {len(successful_trainings)} IAs: '
            success_msg += ', '.join(t['ai_name'] for t in successful_trainings)
            messages.success(request, success_msg)
            
        if failed_trainings:
            fail_msg = f'Falha ao iniciar treinamento para {len(failed_trainings)} IAs:\n'
            for fail in failed_trainings:
                fail_msg += f"\n- {fail['ai_name']}: {fail.get('error', 'Erro desconhecido')}"
            messages.error(request, fail_msg)

        if not successful_trainings:
            return JsonResponse({'success': False}, status=500)

        return JsonResponse({'success': True})

    except Exception as e:
        logger.exception("Erro durante o treinamento:")
        messages.error(request, f'Erro durante o treinamento: {str(e)}')
        return JsonResponse({'success': False}, status=500)

@login_required
def training_monitor(request):
    """Endpoint unificado para monitoramento de treinamento.
    
    Se fornecidos job_ids[] e config_ids[], retorna o status específico desses treinamentos.
    Caso contrário, retorna o status geral de todos os treinamentos.
    """
    user = request.user
    
    # Verifica se há parâmetros específicos de job para um monitoramento detalhado
    job_ids = request.GET.getlist('job_ids[]')
    config_ids = request.GET.getlist('config_ids[]')
    
    if job_ids and config_ids and len(job_ids) == len(config_ids):
        # Lógica da antiga função training_progress
        results = []
        try:
            for job_id, config_id in zip(job_ids, config_ids):
                config = AIClientConfiguration.objects.get(
                    id=config_id,
                    token__user=user
                )
                
                try:
                    client = config.create_api_client_instance()
                    if not client.can_train:
                        results.append({
                            'job_id': job_id,
                            'config_id': config_id,
                            'error': 'IA não suporta treinamento'
                        })
                        continue
                        
                    status = client.get_training_status(job_id)
                    
                    results.append({
                        'job_id': job_id,
                        'config_id': config_id,
                        'completed': status.status in [TrainingStatus.COMPLETED, TrainingStatus.FAILED],
                        'status': status.status.value,
                        'progress': round(status.progress * 100, 2),
                        'error': status.error if status.error else None,
                        'model_name': status.model_name if status.model_name else None
                    })
                except Exception as e:
                    results.append({
                        'job_id': job_id,
                        'config_id': config_id,
                        'error': str(e)
                    })
                    continue
                
            return JsonResponse({'results': results})
            
        except AIClientConfiguration.DoesNotExist:
            return JsonResponse({'error': 'Configuração não encontrada'}, status=404)
        except Exception as e:
            logger.error(f"Erro ao obter progresso do treinamento: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        # Lógica da antiga função training_status
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
            logger.error("Erro ao obter status dos treinamentos", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e),
                'trainings': [],
                'queue_status': {'queued': 0, 'started': 0, 'finished': 0}
            }, status=500)

@login_required
@require_http_methods(["POST"])
def training_cancel(request, training_id):
    """Endpoint para cancelamento de treinamento."""
    if not training_id:
        messages.error(request, 'ID do treinamento não fornecido')
        return JsonResponse({'success': False}, status=400)
        
    try:
        # Encontra o treinamento pelo ID numérico
        training = AITraining.objects.get(
            id=training_id,
            ai_config__user=request.user.id
        )
        
        # Usa o método cancel_training()
        if training.cancel_training():
            messages.success(request, 'Treinamento cancelado com sucesso')
            return JsonResponse({'success': True})
        else:
            messages.error(request, 'Não foi possível cancelar o treinamento. \n Aguarde sua finalização e exclua o modelo.')
            return JsonResponse({'success': False}, status=400)
            
    except AITraining.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado')
        return JsonResponse({'success': False}, status=404)
    except Exception as e:
        logger.error(f"Erro ao cancelar treinamento: {e}")
        messages.error(request, f'Erro ao cancelar treinamento: {str(e)}')
        return JsonResponse({'success': False}, status=500)

@login_required
@require_http_methods(["POST"])
def training_delete(request, training_id):
    """Endpoint para excluir um treinamento."""
    if not training_id:
        messages.error(request, 'ID do treinamento não fornecido')
        return JsonResponse({'error': 'ID do treinamento não fornecido'}, status=400)
        
    try:
        # Encontra o treinamento pelo ID numérico
        training = AITraining.objects.get(
            id=training_id,
            ai_config__user=request.user.id
        )
        
        # Se estiver em andamento, tenta cancelar primeiro
        if training.status == 'in_progress':
            training.cancel_training()
        
        # Remove o registro
        training.delete()
        
        # Adiciona mensagem de sucesso que será exibida após o reload
        messages.success(request, 'Treinamento excluído com sucesso')
        return JsonResponse({'message': 'Treinamento excluído com sucesso'})
            
    except AITraining.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado')
        return JsonResponse({'error': 'Treinamento não encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Erro ao excluir treinamento: {e}")
        messages.error(request, f'Erro ao excluir treinamento: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)