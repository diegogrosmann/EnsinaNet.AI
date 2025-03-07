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
    TrainAIForm,
    TrainingCaptureForm,
)
from ai_config.utils import perform_training
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
        # Debug para verificar o que está chegando no request
        logger.debug(f"POST data: {request.POST}")
        logger.debug(f"Selected IAs: {request.POST.getlist('selected_ais')}")  # Aqui está esperando 'selected_ias'
        
        # Obtém as IAs selecionadas do formulário
        selected_ias = request.POST.getlist('selected_ais', [])
        if not selected_ias:
            messages.warning(request, 'Nenhuma IA selecionada')
            return JsonResponse({'error': 'Nenhuma IA selecionada'}, status=400)

        # Obtém o arquivo de treinamento
        file_id = request.POST.get('file_id')
        if not file_id:
            messages.warning(request, 'Arquivo de treinamento não especificado')
            return JsonResponse({'error': 'Arquivo de treinamento não especificado'}, status=400)

        training_file = get_object_or_404(AITrainingFile, id=file_id, user=request.user)

        # Verifica se todas as IAs pertencem ao usuário
        if not AIClientConfiguration.objects.filter(
            id__in=selected_ias, 
            user=request.user
        ).count() == len(selected_ias):
            messages.error(request, 'Algumas IAs selecionadas não pertencem ao seu usuário')
            return JsonResponse({'error': 'Permissão negada'}, status=403)

        # Inicia o treinamento
        results = perform_training(
            selected_ias=selected_ias,
            training_file=training_file
        )

        # Verifica os resultados do treinamento
        successful_trainings = []
        failed_trainings = []

        for result in results:
            if result.get('status') == 'initiated':
                successful_trainings.append(result)
            else:
                failed_trainings.append(result)

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
def training_status(request):
    """Endpoint para status do treinamento em tempo real."""
    user = request.user
    try:
        trainings = []
        queue_status = {'queued': 0, 'started': 0, 'finished': 0}
        
        active_trainings = AITraining.objects.filter(
            ai_config__token__user=user,
            ai_config__enabled=True
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
                'id': training.job_id,
                'ai_name': training.ai_config.name,
                'file_name': training.file.name if training.file else 'N/A',
                'status': training.status,
                'status_color': _get_status_color(training.status),
                'error': training.error,
                'model_name': training.model_name,
                'progress': training.progress,  # Adiciona o progresso
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
def training_progress(request):
    """Endpoint para monitoramento de progresso de treinamento específico.
    
    Returns:
        JsonResponse: Lista com detalhes do progresso dos treinamentos.
    """
    job_ids = request.GET.getlist('job_ids[]')  # Aceita múltiplos job_ids
    config_ids = request.GET.getlist('config_ids[]')  # Aceita múltiplos config_ids
    
    if not job_ids or not config_ids or len(job_ids) != len(config_ids):
        return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
        
    results = []
    try:
        for job_id, config_id in zip(job_ids, config_ids):
            config = AIClientConfiguration.objects.get(
                id=config_id,
                token__user=request.user
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

@login_required
@require_http_methods(["POST"])
def training_cancel(request, job_id):
    """Endpoint para cancelamento de treinamento."""
    if not job_id:
        messages.error(request, 'ID do job não fornecido')
        return JsonResponse({'success': False}, status=400)
        
    try:
        decoded_job_id = _decode_job_id(job_id)
        # Encontra o treinamento
        training = AITraining.objects.get(
            job_id=decoded_job_id,
            ai_config__token__user=request.user
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
def training_delete(request, job_id):
    """Endpoint para excluir um treinamento."""
    if not job_id:
        messages.error(request, 'ID do job não fornecido')
        return JsonResponse({'error': 'ID do job não fornecido'}, status=400)
        
    try:
        decoded_job_id = _decode_job_id(job_id)
        # Encontra o treinamento
        training = AITraining.objects.get(
            job_id=decoded_job_id,
            ai_config__token__user=request.user
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

def _decode_job_id(encoded_id: str) -> str:
    """Decodifica o job_id da URL.
    
    Args:
        encoded_id (str): ID codificado em base64 url-safe
        
    Returns:
        str: ID decodificado
    """
    try:
        # Substitui caracteres url-safe pelos originais base64
        encoded_id = encoded_id.replace('-', '+').replace('_', '/')
        # Adiciona padding se necessário
        padding = 4 - (len(encoded_id) % 4)
        if padding != 4:
            encoded_id += '=' * padding
        # Decodifica
        return base64.b64decode(encoded_id).decode('utf-8')
    except Exception as e:
        logger.error(f"Erro ao decodificar job_id: {e}")
        raise ValueError(f"ID inválido: {encoded_id}")

def _get_status_color(status):
    """Retorna a cor do bootstrap correspondente ao status."""
    return {
        'not_started': 'secondary',  # cinza
        'in_progress': 'primary',    # azul
        'completed': 'success',      # verde
        'failed': 'danger'          # vermelho
    }.get(status, 'secondary')