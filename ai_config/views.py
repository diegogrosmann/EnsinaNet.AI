import logging
import tempfile
import json
import os
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.forms import formset_factory
from django.views.decorators.http import require_POST
from django.core.files import File
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from accounts.models import UserToken
from api.constants import AIClientType
from api.utils.clientsIA import AI_CLIENT_MAPPING

from .forms import (
    AIClientConfigurationForm, 
    TokenAIConfigurationForm, 
    UserAITrainingFileForm, 
    AIClientTrainingForm,
    TrainAIForm,
    TrainingExampleForm,
    AITrainingFileNameForm,
    TrainingCaptureForm)
from .models import (
    AIClientGlobalConfiguration,
    AIClientConfiguration, 
    TokenAIConfiguration, 
    AIClientTraining,
    AITrainingFile,
    TrainingCapture)
from .utils import perform_training

# Configuração do logger
logger = logging.getLogger(__name__)

@login_required
def manage_ai_configurations(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    forms = []
    for ai_type in AIClientType:
        ai_client_name = ai_type.value
        try:
            ai_client = AIClientGlobalConfiguration.objects.get(api_client_class=ai_client_name)
            ai_client_config = AIClientConfiguration.objects.get(token=token, ai_client=ai_client)
        except AIClientConfiguration.DoesNotExist:
            ai_client_config = AIClientConfiguration(token=token, ai_client=ai_client, enabled=False)
        except AIClientGlobalConfiguration.DoesNotExist:
            logger.error(f"AIClient com api_client_class='{ai_client_name}' não encontrado.")
            messages.error(request, f"Cliente de IA '{ai_client_name}' não configurado. Entre em contato com o administrador.")
            continue

        # Prefix para evitar conflitos de campos nos formulários
        form = AIClientConfigurationForm(instance=ai_client_config, prefix=ai_client_name)
        forms.append({'ai_client': ai_client_name, 'form': form})

    if request.method == 'POST':
        success = True
        for ai_form in forms:
            form = AIClientConfigurationForm(request.POST, request.FILES, instance=ai_form['form'].instance, prefix=ai_form['ai_client'])
            if form.is_valid():
                try:
                    form.save()
                except Exception as e:
                    success = False
                    logger.error(f"Erro ao salvar configurações para {ai_form['ai_client']}: {e}")
                    messages.error(request, f"Erro ao salvar configurações para {ai_form['ai_client']}. Por favor, tente novamente.")
            else:
                success = False
                logger.warning(f"Formulário inválido para {ai_form['ai_client']}: {form.errors}")
                messages.error(request, f"Por favor, corrija os erros nas configurações para {ai_form['ai_client']}.")

        if success:
            messages.success(request, "Configurações de IA salvas com sucesso!")
            return redirect('manage_configurations', token_id=token.id)  # Redireciona para a configuração do token

    context = {'token': token, 'forms': forms}
    return render(request, 'ai_config/manage_ai_configurations.html', context)

@login_required
def manage_token_configurations(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    # Obter ou criar a configuração de IA específica do token
    try:
        token_ai_config = token.ai_configuration
    except TokenAIConfiguration.DoesNotExist:
        token_ai_config = TokenAIConfiguration.objects.create(token=token)

    if request.method == 'POST':
        form = TokenAIConfigurationForm(request.POST, request.FILES, instance=token_ai_config, user=user)
        if form.is_valid():
            try:
                form.save()
                logger.info(f"Configuração TokenAI atualizada para o token '{token.name}' pelo usuário {user.email}.")
                messages.success(request, 'Configurações TokenAI atualizadas com sucesso!')
                return redirect('manage_configurations', token_id=token.id)
            except Exception as e:
                logger.error(f"Erro ao salvar TokenAIConfiguration para o token '{token.name}': {e}")
                messages.error(request, 'Erro ao salvar as configurações TokenAI. Por favor, tente novamente.')
        else:
            logger.warning(f"Formulário TokenAIConfiguration inválido para o token '{token.name}': {form.errors}")
            messages.error(request, 'Por favor, corrija os erros no formulário TokenAI.')
    else:
        form = TokenAIConfigurationForm(instance=token_ai_config, user=user)

    context = {'token': token, 'form': form}
    return render(request, 'ai_config/manage_token_configurations.html', context)

@login_required
def manage_training_configurations(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    ai_client_configs = AIClientConfiguration.objects.filter(token=token)

    forms = []
    for ai_client_config in ai_client_configs:
        ai_client_name = ai_client_config.ai_client.api_client_class
        client_class = AI_CLIENT_MAPPING.get(ai_client_name)
        
        if client_class and client_class.can_train:
            try:
                ai_client_training = AIClientTraining.objects.get(ai_client_configuration=ai_client_config)
            except AIClientTraining.DoesNotExist:
                ai_client_training = AIClientTraining(ai_client_configuration=ai_client_config)

            form = AIClientTrainingForm(instance=ai_client_training, prefix=ai_client_name)
            forms.append({'ai_client': ai_client_name, 'form': form})

    if request.method == 'POST':
        success = True
        for ai_form in forms:
            form = AIClientTrainingForm(request.POST, instance=ai_form['form'].instance, prefix=ai_form['ai_client'])
            if form.is_valid():
                try:
                    form.save()
                except Exception as e:
                    success = False
                    logger.error(f"Erro ao salvar parâmetros de treinamento para {ai_form['ai_client']}: {e}")
                    messages.error(request, f"Erro ao salvar parâmetros de treinamento para {ai_form['ai_client']}. Por favor, tente novamente.")
            else:
                success = False
                logger.warning(f"Formulário inválido para {ai_form['ai_client']}: {form.errors}")
                messages.error(request, f"Por favor, corrija os erros nos parâmetros de treinamento para {ai_form['ai_client']}.")

        if success:
            messages.success(request, "Parâmetros de treinamento salvos com sucesso!")
            return redirect('manage_configurations', token_id=token.id)  # Redireciona para a configuração do token

    context = {'token': token, 'forms': forms}
    return render(request, 'ai_config/manage_training_configurations.html', context)

@login_required
def train_ai(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    # Obter as configurações de IA habilitadas para o token
    ai_client_configs = AIClientConfiguration.objects.filter(token=token, enabled=True)

    # Listas para IAs treináveis e não treináveis
    ai_clients_trainable = []
    ai_clients_not_trainable = []

    # Obter as classes de IA correspondentes
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

    logger.debug(f"AI Clients treináveis: {[cls['name'] for cls in ai_clients_trainable]}")
    logger.debug(f"AI Clients não treináveis: {ai_clients_not_trainable}")

    if request.method == 'POST':
        form = TrainAIForm(request.POST, ai_clients=[client['name'] for client in ai_clients_trainable])
        if not form.is_valid():
            messages.error(request, "Por favor, corrija os erros no formulário.")
            return redirect('ai_config:train_ai', token_id=token.id)

        selected_ias = form.cleaned_data['ai_clients_to_train']

        if not selected_ias:
            messages.warning(request, "Nenhuma IA selecionada.")
            return redirect('ai_config:train_ai', token_id=token.id)

        action = request.POST.get('action')

        if action == 'train':
            # Usar a função perform_training com as IAs selecionadas
            results = perform_training(user, token, selected_ias=selected_ias)
            for ai_name, res in results.items():
                messages.info(request, f"{ai_name}: {res}")
            return redirect('ai_config:train_ai', token_id=token.id)
        elif action == 'remove_model':
            # Remover modelos treinados das IAs selecionadas
            for ai_client_name in selected_ias:
                try:
                    # Obter a configuração global do cliente de IA
                    ai_client = AIClientGlobalConfiguration.objects.get(api_client_class=ai_client_name)
                except AIClientGlobalConfiguration.DoesNotExist:
                    messages.error(request, f"Cliente de IA '{ai_client_name}' não encontrado.")
                    continue

                try:
                    # Obter a configuração específica do cliente de IA para o token
                    ai_client_config = ai_client_configs.get(ai_client__api_client_class=ai_client_name)
                    ai_training = ai_client_config.training

                    if ai_training.trained_model_name:
                        ai_training.trained_model_name = None  # ou '' dependendo da preferência
                        ai_training.save()
                        messages.success(request, f"Modelo treinado para '{ai_client_name}' removido com sucesso.")
                    else:
                        messages.info(request, f"Nenhum modelo treinado encontrado para '{ai_client_name}'.")
                except AIClientConfiguration.DoesNotExist:
                    messages.error(request, f"Configuração de IA para '{ai_client_name}' não encontrada.")
                except Exception as e:
                    logger.error(f"Erro ao remover o modelo treinado para {ai_client_name}: {e}")
                    messages.error(request, f"Erro ao remover o modelo treinado para '{ai_client_name}'. Por favor, tente novamente.")

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
def upload_training_file(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    if request.method == 'POST':
        form = UserAITrainingFileForm(request.POST, request.FILES)
        if form.is_valid():
            training_file = form.save(commit=False)
            training_file.user = user
            training_file.save()
            logger.info(f"Arquivo de treinamento carregado pelo usuário {user.email}.")
            messages.success(request, 'Arquivo de treinamento carregado com sucesso!')
            return redirect('manage_tokens')
        else:
            logger.warning(f"Formulário de upload de arquivo de treinamento inválido: {form.errors}")
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        form = UserAITrainingFileForm()

    context = {'token': token, 'form': form}
    return render(request, 'ai_config/upload_training_file.html', context)

TrainingExampleFormSetFactory = formset_factory(
    TrainingExampleForm,
    can_delete=True,
    extra=0
)

@login_required
def create_or_edit_training_file(request, file_id=None):
    user = request.user
    training_file = None
    initial_data = []
    initial_name = ''

    if file_id:
        # Editando um arquivo existente
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        initial_name = training_file.name
        try:
            with training_file.file.open('rb') as f:
                content = f.read().decode('utf-8')
                data = json.loads(content)
                for example in data:
                    system_message = example.get('system_message', '').strip()
                    user_message = example.get('user_message', '').strip()
                    response = example.get('response', '').strip()
                    initial_data.append({
                        'system_message': system_message,
                        'user_message': user_message,
                        'response': response
                    })
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON no arquivo de treinamento: {e}")
            messages.error(request, 'O arquivo de treinamento está corrompido ou não está no formato JSON válido.')
            return redirect('manage_tokens')
        except Exception as e:
            logger.error(f"Erro ao abrir o arquivo de treinamento: {e}")
            messages.error(request, 'Erro ao abrir o arquivo de treinamento.')
            return redirect('manage_tokens')
        
        # Formset para edição - sem formulários extras
        TrainingExampleFormSetEdit = formset_factory(
            TrainingExampleForm,
            can_delete=True,
            extra=0
        )
        formset = TrainingExampleFormSetEdit(initial=initial_data, prefix='form')
        name_form = AITrainingFileNameForm(initial={'name': initial_name, 'token': training_file.user.id}, prefix='name')
    else:
        # Criando um novo arquivo - inicializa com 1 formulário
        TrainingExampleFormSetCreate = formset_factory(
            TrainingExampleForm,
            can_delete=True,
            extra=1
        )
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
                    system_message = form.cleaned_data.get('system_message', '').strip()
                    user_message = form.cleaned_data.get('user_message', '').strip()
                    response = form.cleaned_data.get('response', '').strip()
                    example = {
                        'system_message': system_message,
                        'user_message': user_message,
                        'response': response
                    }
                    examples.append(example)
            
            if not examples:
                messages.error(request, 'Por favor, adicione pelo menos um exemplo.')
            else:
                # Criar um arquivo temporário com os exemplos
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as temp_file:
                    json.dump(examples, temp_file, ensure_ascii=False, indent=4)
                    temp_file_path = temp_file.name
                
                try:
                    if training_file:
                        # Atualizar o arquivo existente
                        existing_file_name = os.path.basename(training_file.file.name)
                        with open(temp_file_path, 'rb') as f:
                            training_file.file.save(existing_file_name, File(f), save=True)
                        # Atualizar o nome, se necessário
                        if training_file.name != name:
                            training_file.name = name
                            training_file.save()
                        messages.success(request, 'Arquivo de treinamento atualizado com sucesso!')
                        if 'save_and_continue' in request.POST:
                            return redirect('ai_config:edit_training_file', file_id=training_file.id)
                        else:
                            return redirect('manage_tokens')
                    else:
                        # Verificar se o nome já existe para o usuário
                        if AITrainingFile.objects.filter(user=user, name=name).exists():
                            messages.error(request, 'Você já possui um arquivo de treinamento com este nome.')
                            os.remove(temp_file_path)
                            return render(request, 'ai_config/create_training_file.html', {'formset': formset, 'name_form': name_form, 'capture_form': TrainingCaptureForm(prefix='capture', user=user)})
                        
                        # Gerar um nome de arquivo único
                        unique_filename = f"{name}_{uuid.uuid4().hex}.json"
                        with open(temp_file_path, 'rb') as f:
                            training_file = AITrainingFile.objects.create(
                                user=user,
                                name=name,
                                file=File(f, name=unique_filename)
                            )
                        messages.success(request, 'Arquivo de treinamento criado com sucesso!')
                        if 'save_and_continue' in request.POST:
                            return redirect('ai_config:edit_training_file', file_id=training_file.id)
                        else:
                            return redirect('manage_tokens')
                except Exception as e:
                    logger.error(f"Erro ao salvar o arquivo de treinamento: {e}")
                    messages.error(request, 'Erro ao salvar o arquivo de treinamento.')
                finally:
                    # Remover o arquivo temporário
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
        else:
            if not name_form.is_valid():
                messages.error(request, 'Por favor, corrija os erros no campo de nome.')
            if not formset.is_valid():
                messages.error(request, 'Por favor, corrija os erros nos exemplos.')
    else:
        # GET request
        pass

    # Obter a captura ativa para o usuário atual
    active_capture = TrainingCapture.objects.filter(token__user=user, is_active=True).first()
    if active_capture:
        # Verificar se last_activity tem mais de 1 minuto
        time_difference = timezone.now() - active_capture.last_activity
        if time_difference > timedelta(minutes=1):
            # Desativar a captura
            active_capture.is_active = False
            active_capture.save()
            active_capture = None  # Não há captura ativa após desativar
            # Inicializar o formulário de captura sem instância
            capture_form = TrainingCaptureForm(prefix='capture', user=user)
        else:
            # Preencher o formulário de captura com a captura ativa
            capture_form = TrainingCaptureForm(instance=active_capture, prefix='capture', user=user)
    else:
        # Inicializar o formulário de captura sem instância
        capture_form = TrainingCaptureForm(prefix='capture', user=user)

    context = {
        'formset': formset,
        'name_form': name_form,
        'training_file': training_file,
        'capture_form': capture_form,
        'active_capture': active_capture
    }
    return render(request, 'ai_config/create_training_file.html', context)

@login_required
def download_training_file(request, file_id):
    user = request.user
    training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
    response = FileResponse(training_file.file.open('rb'), as_attachment=True, filename=training_file.file.name)
    return response

@login_required
def delete_training_file(request, file_id):
    user = request.user
    training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
    if request.method == 'POST':
        file_path = training_file.file.path
        training_file.file.delete()
        logger.debug(f"Arquivo físico deletado: {file_path}")
        training_file.delete()
        messages.success(request, 'Arquivo de treinamento excluído com sucesso!')
        return redirect('manage_tokens')
    else:
        context = {'training_file': training_file}
        return render(request, 'ai_config/confirm_delete_training_file.html', context)

@login_required
@require_POST
def toggle_capture(request):
    token_id = request.POST.get('token_id')
    ai_client_name = request.POST.get('ai_client_id')
    action = request.POST.get('action')

    token = get_object_or_404(UserToken, id=token_id, user=request.user)
    ai_client = get_object_or_404(AIClientGlobalConfiguration, api_client_class=ai_client_name)

    capture, created = TrainingCapture.objects.get_or_create(token=token, ai_client=ai_client)

    if action == 'activate':
        # Desativar todas as outras capturas ativas do mesmo usuário
        TrainingCapture.objects.filter(is_active=True, token__user=request.user).exclude(id=capture.id).update(is_active=False)

        if not capture.is_active:
            capture.is_active = True
            if not capture.temp_file:
                # Criar um arquivo temporário
                temp_filename = f'temp_capture_{uuid.uuid4().hex}.json'
                temp_file_path = os.path.join(settings.MEDIA_ROOT, 'training_captures', temp_filename)
                
                # Inicializar o arquivo como uma lista vazia
                with open(temp_file_path, 'w') as temp_file:
                    json.dump([], temp_file)
                
                # Salvar o arquivo no campo temp_file
                with open(temp_file_path, 'rb') as f:
                    capture.temp_file.save(temp_filename, File(f), save=True)
                
                # Remover o arquivo temporário após salvar via Django
                os.remove(temp_file_path)
            capture.save()
            status = 'ativada'
        else:
            status = 'já estava ativada'
    elif action == 'deactivate':
        if capture.is_active:
            capture.is_active = False
            capture.save()
            status = 'desativada'
        else:
            status = 'já estava desativada'
    else:
        return JsonResponse({'error': 'Ação inválida.'}, status=400)

    return JsonResponse({'message': f'Captura {status} com sucesso.'})

@login_required
def get_training_examples(request, token_id, ai_client_name):
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
        # Limpar o arquivo temporário
        with temp_file.open('w') as f:
            json.dump([], f)
        return JsonResponse({'examples': training_data})
    except TrainingCapture.DoesNotExist:
        return JsonResponse({'error': 'Captura não está ativa.'}, status=400)
    except Exception as e:
        logger.error(f"Erro ao carregar os exemplos: {e}")
        return JsonResponse({'error': 'Erro ao carregar os exemplos.'}, status=500)