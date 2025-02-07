import logging
import tempfile
import json
import os
import uuid
import time
from datetime import timedelta
from typing import Any, Dict, Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse, HttpRequest, HttpResponse
from django.forms import formset_factory
from django.views.decorators.http import require_POST
from django.core.files import File
from django.conf import settings
from django.utils import timezone

from accounts.models import UserToken
from api.utils.clientsIA import AI_CLIENT_MAPPING

from .forms import (
    AIClientConfigurationForm,
    TokenAIConfigurationForm,
    UserAITrainingFileForm,
    AIClientTrainingForm,
    TrainAIForm,
    TrainingExampleForm,
    AITrainingFileNameForm,
    TrainingCaptureForm,
)
from .models import (
    AIClientGlobalConfiguration,
    AIClientConfiguration,
    TokenAIConfiguration,
    AIClientTraining,
    AITrainingFile,
    TrainingCapture,
)
from .utils import perform_training

logger = logging.getLogger(__name__)


@login_required
def manage_ai_configurations(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Exibe as configurações de IA associadas a um token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_configs = AIClientConfiguration.objects.filter(token=token)
    context: Dict[str, Any] = {'token': token, 'ai_configs': ai_configs}
    return render(request, 'ai_config/manage_ai_configurations.html', context)


@login_required
def create_ai_configuration(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Cria uma nova configuração de IA para o token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    if request.method == 'POST':
        form = AIClientConfigurationForm(request.POST)
        if form.is_valid():
            config_obj = form.save(commit=False)
            config_obj.token = token
            try:
                config_obj.save()
                messages.success(request, "Nova configuração de IA criada com sucesso!")
                return redirect('ai_config:manage_ai_configurations', token_id=token.id)
            except Exception as e:
                logger.exception("Erro ao salvar configuração de IA:")
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
    else:
        form = AIClientConfigurationForm()
    context = {'token': token, 'form': form}
    return render(request, 'ai_config/create_ai_configuration.html', context)


@login_required
def edit_ai_configuration(request: HttpRequest, token_id: str, config_id: int) -> HttpResponse:
    """
    Edita uma configuração de IA existente.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_config = get_object_or_404(AIClientConfiguration, id=config_id, token=token)
    if request.method == 'POST':
        form = AIClientConfigurationForm(request.POST, instance=ai_config)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Configuração de IA atualizada com sucesso!")
                return redirect('ai_config:manage_ai_configurations', token_id=token.id)
            except Exception as e:
                logger.exception("Erro ao atualizar configuração de IA:")
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
    else:
        form = AIClientConfigurationForm(instance=ai_config)
    context = {'token': token, 'form': form, 'ai_config': ai_config}
    return render(request, 'ai_config/edit_ai_configuration.html', context)


@login_required
def delete_ai_configuration(request: HttpRequest, token_id: str, config_id: int) -> HttpResponse:
    """
    Exclui uma configuração de IA.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_config = get_object_or_404(AIClientConfiguration, id=config_id, token=token)
    if request.method == 'POST':
        name = ai_config.name
        ai_config.delete()
        messages.success(request, f"A configuração '{name}' foi deletada.")
        return redirect('ai_config:manage_ai_configurations', token_id=token.id)
    context = {'token': token, 'ai_config': ai_config}
    return render(request, 'ai_config/delete_ai_configuration.html', context)


@login_required
def manage_token_configurations(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Gerencia a configuração de prompt para o token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    token_ai_config, _ = TokenAIConfiguration.objects.get_or_create(token=token)
    if request.method == 'POST':
        form = TokenAIConfigurationForm(request.POST, request.FILES, instance=token_ai_config, user=user)
        if form.is_valid():
            try:
                form.save()
                logger.info(f"Configuração TokenAI atualizada para o token '{token.name}'")
                messages.success(request, 'Configurações TokenAI atualizadas com sucesso!')
                return redirect('manage_configurations', token_id=token.id)
            except Exception as e:
                logger.exception("Erro ao salvar TokenAIConfiguration:")
                messages.error(request, 'Erro ao salvar as configurações TokenAI. Tente novamente.')
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
            messages.error(request, 'Corrija os erros no formulário TokenAI.')
    else:
        form = TokenAIConfigurationForm(instance=token_ai_config, user=user)
    context = {'token': token, 'form': form}
    return render(request, 'ai_config/manage_token_configurations.html', context)


@login_required
def manage_training_configurations(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Gerencia os parâmetros de treinamento para as configurações de IA associadas ao token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_client_configs = AIClientConfiguration.objects.filter(token=token)
    forms_list = []
    for ai_client_config in ai_client_configs:
        ai_client_name = ai_client_config.ai_client.api_client_class
        client_class = AI_CLIENT_MAPPING.get(ai_client_name)
        if client_class and client_class.can_train:
            try:
                ai_client_training = AIClientTraining.objects.get(ai_client_configuration=ai_client_config)
            except AIClientTraining.DoesNotExist:
                ai_client_training = AIClientTraining(ai_client_configuration=ai_client_config)
            form = AIClientTrainingForm(instance=ai_client_training, prefix=ai_client_name)
            forms_list.append({'ai_client': ai_client_name, 'form': form})
    if request.method == 'POST':
        success = True
        for ai_form in forms_list:
            form = AIClientTrainingForm(request.POST, instance=ai_form['form'].instance, prefix=ai_form['ai_client'])
            if form.is_valid():
                try:
                    form.save()
                except Exception as e:
                    success = False
                    logger.exception(f"Erro ao salvar parâmetros para {ai_form['ai_client']}:")
                    messages.error(request, f"Erro ao salvar parâmetros para {ai_form['ai_client']}.")
            else:
                success = False
                logger.warning(f"Formulário inválido para {ai_form['ai_client']}: {form.errors}")
                messages.error(request, f"Corrija os erros para {ai_form['ai_client']}.")
        if success:
            messages.success(request, "Parâmetros de treinamento salvos com sucesso!")
            return redirect('manage_configurations', token_id=token.id)
    context = {'token': token, 'forms': forms_list}
    return render(request, 'ai_config/manage_training_configurations.html', context)


@login_required
def train_ai(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Treina as IAs selecionadas para o token.
    """
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


@login_required
def upload_training_file(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Faz upload de um arquivo de treinamento para o token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    if request.method == 'POST':
        form = UserAITrainingFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                training_file = form.save(commit=False)
                training_file.user = user
                training_file.save()
                logger.info(f"Arquivo de treinamento carregado por {user.email}")
                messages.success(request, 'Arquivo carregado com sucesso!')
                return redirect('manage_tokens')
            except Exception as e:
                logger.exception("Erro ao carregar arquivo de treinamento:")
                messages.error(request, 'Erro ao carregar arquivo.')
        else:
            logger.warning(f"Formulário de upload inválido: {form.errors}")
            messages.error(request, 'Corrija os erros no formulário.')
    else:
        form = UserAITrainingFileForm()
    context = {'token': token, 'form': form}
    return render(request, 'ai_config/upload_training_file.html', context)


TrainingExampleFormSetFactory = formset_factory(TrainingExampleForm, can_delete=True, extra=0)


@login_required
def create_or_edit_training_file(request: HttpRequest, file_id: Optional[int] = None) -> HttpResponse:
    """
    Cria ou edita um arquivo de treinamento.
    """
    user = request.user
    training_file = None
    initial_data = []
    initial_name = ''
    if file_id:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        initial_name = training_file.name
        try:
            with training_file.file.open('rb') as f:
                content = f.read().decode('utf-8')
                data = json.loads(content)
                for example in data:
                    initial_data.append({
                        'system_message': example.get('system_message', '').strip(),
                        'user_message': example.get('user_message', '').strip(),
                        'response': example.get('response', '').strip()
                    })
        except json.JSONDecodeError as e:
            logger.exception("Erro ao decodificar JSON:")
            messages.error(request, 'Arquivo corrompido ou formato inválido.')
            return redirect('manage_tokens')
        except Exception as e:
            logger.exception("Erro ao abrir arquivo de treinamento:")
            messages.error(request, 'Erro ao abrir arquivo.')
            return redirect('manage_tokens')
        TrainingExampleFormSetEdit = formset_factory(TrainingExampleForm, can_delete=True, extra=0)
        formset = TrainingExampleFormSetEdit(initial=initial_data, prefix='form')
        name_form = AITrainingFileNameForm(initial={'name': initial_name, 'token': training_file.user.id}, prefix='name')
    else:
        TrainingExampleFormSetCreate = formset_factory(TrainingExampleForm, can_delete=True, extra=1)
        formset = TrainingExampleFormSetCreate(request.POST or None, prefix='form')
        name_form = AITrainingFileNameForm(prefix='name')
    if request.method == 'POST':
        name_form = AITrainingFileNameForm(request.POST, prefix='name')
        formset = TrainingExampleFormSetFactory(request.POST, prefix='form')
        if name_form.is_valid() and formset.is_valid():
            name = name_form.cleaned_data['name']
            examples = []
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    examples.append({
                        'system_message': form.cleaned_data.get('system_message', '').strip(),
                        'user_message': form.cleaned_data.get('user_message', '').strip(),
                        'response': form.cleaned_data.get('response', '').strip()
                    })
            if not examples:
                messages.error(request, 'Adicione pelo menos um exemplo.')
            else:
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as temp_file:
                    json.dump(examples, temp_file, ensure_ascii=False, indent=4)
                    temp_file_path = temp_file.name
                try:
                    if training_file:
                        existing_file_name = os.path.basename(training_file.file.name)
                        with open(temp_file_path, 'rb') as f:
                            training_file.file.save(existing_file_name, File(f), save=True)
                        if training_file.name != name:
                            training_file.name = name
                            training_file.save()
                        messages.success(request, 'Arquivo atualizado com sucesso!')
                        if 'save_and_continue' in request.POST:
                            return redirect('ai_config:edit_training_file', file_id=training_file.id)
                        else:
                            return redirect('manage_tokens')
                    else:
                        if AITrainingFile.objects.filter(user=user, name=name).exists():
                            messages.error(request, 'Já existe um arquivo com este nome.')
                            os.remove(temp_file_path)
                            return render(request, 'ai_config/create_training_file.html', {
                                'formset': formset,
                                'name_form': name_form,
                                'capture_form': TrainingCaptureForm(prefix='capture', user=user)
                            })
                        unique_filename = f"{name}_{uuid.uuid4().hex}.json"
                        with open(temp_file_path, 'rb') as f:
                            training_file = AITrainingFile.objects.create(
                                user=user,
                                name=name,
                                file=File(f, name=unique_filename)
                            )
                        messages.success(request, 'Arquivo criado com sucesso!')
                        if 'save_and_continue' in request.POST:
                            return redirect('ai_config:edit_training_file', file_id=training_file.id)
                        else:
                            return redirect('manage_tokens')
                except Exception as e:
                    logger.exception("Erro ao salvar arquivo de treinamento:")
                    messages.error(request, 'Erro ao salvar arquivo.')
                finally:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
        else:
            if not name_form.is_valid():
                messages.error(request, 'Corrija os erros no campo de nome.')
            if not formset.is_valid():
                messages.error(request, 'Corrija os erros nos exemplos.')
    active_capture = TrainingCapture.objects.filter(token__user=user, is_active=True).first()
    if active_capture:
        time_difference = timezone.now() - active_capture.last_activity
        if time_difference > timedelta(minutes=1):
            active_capture.is_active = False
            active_capture.save()
            active_capture = None
            capture_form = TrainingCaptureForm(prefix='capture', user=user)
        else:
            capture_form = TrainingCaptureForm(instance=active_capture, prefix='capture', user=user)
    else:
        capture_form = TrainingCaptureForm(prefix='capture', user=user)
    context = {
        'formset': formset,
        'name_form': name_form,
        'training_file': training_file,
        'capture_form': capture_form,
        'active_capture': active_capture,
    }
    return render(request, 'ai_config/create_training_file.html', context)


@login_required
def download_training_file(request: HttpRequest, file_id: int) -> HttpResponse:
    """
    Permite o download de um arquivo de treinamento.
    """
    user = request.user
    training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
    response = FileResponse(training_file.file.open('rb'), as_attachment=True, filename=training_file.file.name)
    return response


@login_required
def delete_training_file(request: HttpRequest, file_id: int) -> HttpResponse:
    """
    Exibe a confirmação e processa a exclusão de um arquivo de treinamento.
    """
    user = request.user
    training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
    if request.method == 'POST':
        file_path = training_file.file.path
        training_file.file.delete()
        logger.debug(f"Arquivo físico deletado: {file_path}")
        training_file.delete()
        messages.success(request, 'Arquivo excluído com sucesso!')
        return redirect('manage_tokens')
    context = {'training_file': training_file}
    return render(request, 'ai_config/confirm_delete_training_file.html', context)


@login_required
@require_POST
def toggle_capture(request: HttpRequest) -> JsonResponse:
    """
    Ativa ou desativa a captura de exemplos de treinamento.
    """
    token_id = request.POST.get('token_id')
    ai_client_name = request.POST.get('ai_client_id')
    action = request.POST.get('action')
    token = get_object_or_404(UserToken, id=token_id, user=request.user)
    ai_client = get_object_or_404(AIClientGlobalConfiguration, api_client_class=ai_client_name)
    capture, _ = TrainingCapture.objects.get_or_create(token=token, ai_client=ai_client)
    if action == 'activate':
        TrainingCapture.objects.filter(is_active=True, token__user=request.user).exclude(id=capture.id).update(is_active=False)
        if not capture.is_active:
            capture.is_active = True
            if not capture.temp_file:
                temp_filename = f'temp_capture_{uuid.uuid4().hex}.json'
                temp_file_path = os.path.join(settings.MEDIA_ROOT, 'training_captures', temp_filename)
                with open(temp_file_path, 'w') as temp_file:
                    json.dump([], temp_file)
                with open(temp_file_path, 'rb') as f:
                    capture.temp_file.save(temp_filename, File(f), save=True)
                os.remove(temp_file_path)
            capture.save()
            status_msg = 'ativada'
        else:
            status_msg = 'já estava ativada'
    elif action == 'deactivate':
        if capture.is_active:
            capture.is_active = False
            capture.save()
            status_msg = 'desativada'
        else:
            status_msg = 'já estava desativada'
    else:
        return JsonResponse({'error': 'Ação inválida.'}, status=400)
    return JsonResponse({'message': f'Captura {status_msg} com sucesso.'})


@login_required
def get_training_examples(request: HttpRequest, token_id: str, ai_client_name: str) -> JsonResponse:
    """
    Retorna os exemplos de treinamento capturados para uma determinada IA.
    """
    token = get_object_or_404(UserToken, id=token_id, user=request.user)
    ai_client = get_object_or_404(AIClientGlobalConfiguration, api_client_class=ai_client_name)
    try:
        capture = TrainingCapture.objects.get(token=token, ai_client=ai_client, is_active=True)
        capture.save() 
        temp_file = capture.temp_file
        if not temp_file:
            return JsonResponse({'examples': []})
        with temp_file.open('r') as f:
            training_data = json.load(f)
        with temp_file.open('w') as f:
            json.dump([], f)
        return JsonResponse({'examples': training_data})
    except TrainingCapture.DoesNotExist:
        return JsonResponse({'error': 'Captura não está ativa.'}, status=400)
    except Exception as e:
        logger.exception("Erro ao carregar exemplos:")
        return JsonResponse({'error': 'Erro ao carregar exemplos.'}, status=500)


@login_required
@require_POST
def toggle_ai_configuration(request: HttpRequest, token_id: str, config_id: int) -> JsonResponse:
    """
    Alterna o estado (enabled/disabled) de uma configuração de IA.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_config = get_object_or_404(AIClientConfiguration, id=config_id, token=token)
    data = json.loads(request.body)
    ai_config.enabled = data.get('enabled', False)
    ai_config.save()
    return JsonResponse({
        'status': 'success',
        'enabled': ai_config.enabled,
        'config_id': config_id
    })
