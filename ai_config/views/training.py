import logging
import json
import os
import tempfile
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse, FileResponse
from django.core.files import File
from django.views.decorators.http import require_POST
from django.forms import formset_factory

from accounts.models import UserToken
from ai_config.models import (
    AIClientGlobalConfiguration,
    AIClientConfiguration,
    AIClientTraining,
    AITrainingFile,
    TrainingCapture
)
from ai_config.forms import (
    AIClientTrainingForm,
    TrainAIForm,
    TrainingExampleForm,
    AITrainingFileNameForm,
    TrainingCaptureForm,
)
from ai_config.utils import perform_training
from api.utils.clientsIA import AI_CLIENT_MAPPING

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
    available_ais = AIClientGlobalConfiguration.objects.all()
    
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
        'available_ais': available_ais,
        'active_capture': active_capture,
        'form': TrainingCaptureForm(user=user) if not active_capture else None,
    }
    
    return render(request, 'training/center.html', context)

@login_required
def training_ai(request: HttpRequest, token_id: str) -> HttpResponse:
    """Realiza o treinamento das IAs selecionadas para o token."""
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_client_configs = AIClientConfiguration.objects.filter(token=token, enabled=True)
    ai_clients_trainable = []
    ai_clients_not_trainable = []
    
    for ai_client_config in ai_client_configs:
        ai_client_name = ai_client_config.ai_client.api_client_class
        client_class = AI_CLIENT_MAPPING.get(ai_client_name)
        if client_class:
            if client_class.can_train:
                ai_clients_trainable.append({
                    'name': ai_client_name,
                    'trained_model_name': ai_client_config.training.trained_model_name if hasattr(ai_client_config, 'training') else None
                })
            else:
                ai_clients_not_trainable.append(ai_client_name)
    
    if request.method == 'POST':
        form = TrainAIForm(request.POST, ai_clients=[client['name'] for client in ai_clients_trainable])
        if not form.is_valid():
            messages.error(request, "Corrija os erros no formulário.")
            return redirect('ai_config:train_ai', token_id=token.id)
        
        selected_ias = form.cleaned_data['ai_clients_to_train']
        if not selected_ias:
            messages.warning(request, "Nenhuma IA selecionada.")
            return redirect('ai_config:train_ai', token_id=token.id)
        
        action = request.POST.get('action')
        if action == 'train':
            results = perform_training(user, token, selected_ias=selected_ias)
            for ai_name, res in results.items():
                messages.info(request, f"{ai_name}: {res}")
            return redirect('ai_config:train_ai', token_id=token.id)
        elif action == 'remove_model':
            for ai_client_name in selected_ias:
                try:
                    ai_client = AIClientGlobalConfiguration.objects.get(api_client_class=ai_client_name)
                except AIClientGlobalConfiguration.DoesNotExist:
                    messages.error(request, f"Cliente de IA '{ai_client_name}' não encontrado.")
                    continue
                try:
                    ai_client_config = ai_client_configs.get(ai_client__api_client_class=ai_client_name)
                    ai_training = ai_client_config.training
                    if ai_training.trained_model_name:
                        ai_training.trained_model_name = None
                        ai_training.save()
                        messages.success(request, f"Modelo para '{ai_client_name}' removido com sucesso.")
                    else:
                        messages.info(request, f"Nenhum modelo encontrado para '{ai_client_name}'.")
                except Exception as e:
                    logger.exception(f"Erro ao remover modelo para {ai_client_name}:")
                    messages.error(request, f"Erro ao remover modelo para '{ai_client_name}'.")
            return redirect('ai_config:train_ai', token_id=token.id)
    else:
        form = TrainAIForm(ai_clients=[client['name'] for client in ai_clients_trainable])
    
    context = {
        'token': token,
        'form': form,
        'ai_clients_not_trainable': ai_clients_not_trainable,
        'ai_clients_trainable_details': ai_clients_trainable,
    }
    return render(request, 'ai_config/train_ai.html', context)