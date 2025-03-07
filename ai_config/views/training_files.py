import logging
import json
import os
from typing import Optional, Tuple, List, Dict
import uuid
import tempfile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse, FileResponse
from django.core.files import File
from django.forms import formset_factory

from accounts.models import UserToken
from ai_config.models import AITrainingFile, TrainingCapture, AIClientGlobalConfiguration
from ai_config.forms import (
    TrainingExampleForm,
    AITrainingFileNameForm,
    TrainingCaptureForm
)

logger = logging.getLogger(__name__)

def validate_training_file_format(file) -> Tuple[bool, str, List[Dict]]:
    """
    Valida o formato do arquivo de treinamento.
    Retorna: (is_valid, error_message, data)
    """
    try:
        content = file.read()
        file.seek(0)  # Reset file pointer
        data = json.loads(content)
        
        if not isinstance(data, list):
            return False, "O arquivo deve conter uma lista de exemplos", []
        
        for idx, example in enumerate(data, 1):
            if not isinstance(example, dict):
                return False, f"O exemplo {idx} deve ser um objeto", []
            
            # system_message é opcional
            required_fields = {'user_message', 'response'}
            missing_fields = required_fields - set(example.keys())
            
            if missing_fields:
                return False, f"Exemplo {idx} está faltando campos: {', '.join(missing_fields)}", []
            
            # Adiciona system_message vazio se não existir
            if 'system_message' not in example:
                example['system_message'] = ''
            
            # Valida tipos dos campos
            all_fields = {'system_message', 'user_message', 'response'}
            if not all(isinstance(example.get(field, ''), str) for field in all_fields):
                return False, f"Exemplo {idx} contém campos que não são texto", []
            
            # Apenas user_message e response não podem ser vazios
            if not all(example[field].strip() for field in required_fields):
                return False, f"Exemplo {idx} contém campos obrigatórios vazios", []
    
        return True, "", data
    except json.JSONDecodeError:
        return False, "Arquivo JSON inválido", []
    except Exception as e:
        return False, f"Erro ao validar arquivo: {str(e)}", []

@login_required
def training_file_upload(request):
    """Processa o upload de um arquivo de treinamento."""
    if request.method == 'POST':
        try:
            user = request.user
            name = request.POST.get('name')
            file = request.FILES.get('file')

            if not file or not name:
                return JsonResponse({
                    'error': 'Nome do arquivo e arquivo são obrigatórios'
                }, status=400)

            # Valida o formato do arquivo
            is_valid, error_message, _ = validate_training_file_format(file)
            if not is_valid:
                return JsonResponse({'error': error_message}, status=400)

            # Gera um nome único para o arquivo
            extension = file.name.split('.')[-1] if '.' in file.name else ''
            unique_filename = f"{uuid.uuid4().hex[:8]}_{name}.{extension}"
            file.name = unique_filename

            # Verifica se já existe um arquivo com este nome
            if AITrainingFile.objects.filter(user=user, name=name).exists():
                return JsonResponse({
                    'error': 'Já existe um arquivo com este nome'
                }, status=400)

            # Cria novo arquivo de treinamento
            training_file = AITrainingFile(
                user=user,
                name=name,
                file=file
            )
            training_file.save()

            return JsonResponse({
                'success': True,
                'message': 'Arquivo enviado com sucesso',
                'id': training_file.id,
                'name': training_file.name
            })
            
        except Exception as e:
            logger.error(f"Erro no upload do arquivo: {str(e)}")
            return JsonResponse({
                'error': 'Erro ao processar o upload do arquivo'
            }, status=500)
    
    return JsonResponse({'error': 'Método não permitido'}, status=405)

@login_required
def training_file_create(request: HttpRequest, file_id: Optional[int] = None) -> HttpResponse:
    """Cria ou edita um arquivo de treinamento."""
    user = request.user
    training_file = None
    initial_data = []
    initial_name = ''
    
    if file_id:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        initial_name = training_file.name
        try:
            with training_file.file.open('r') as f:
                is_valid, error_message, data = validate_training_file_format(f)
                if not is_valid:
                    messages.error(request, f'Arquivo inválido: {error_message}')
                    return redirect('ai_config:training_center')
                initial_data = data
        except Exception as e:
            logger.exception("Erro ao abrir arquivo de treinamento:")
            messages.error(request, 'Erro ao abrir arquivo.')
            return redirect('ai_config:training_center')
        
    formset_class = formset_factory(TrainingExampleForm, can_delete=True, extra=0 if file_id else 1)
    name_form = AITrainingFileNameForm(initial={'name': initial_name} if file_id else None, prefix='name')
    formset = formset_class(initial=initial_data, prefix='form')
    
    if request.method == 'POST':
        name_form = AITrainingFileNameForm(request.POST, prefix='name')
        formset = formset_class(request.POST, prefix='form')
        if name_form.is_valid() and formset.is_valid():
            name = name_form.cleaned_data['name']
            examples = []
            for form in formset:
                if form.is_valid() and form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    examples.append({
                        'system_message': form.cleaned_data.get('system_message', '').strip(),
                        'user_message': form.cleaned_data.get('user_message', '').strip(),
                        'response': form.cleaned_data.get('response', '').strip()
                    })
            if not examples:
                messages.error(request, 'Adicione pelo menos um exemplo.')
                context = {
                    'formset': formset,
                    'name_form': name_form,
                    'capture_form': TrainingCaptureForm(prefix='capture', user=user)
                }
                return render(request, 'training/file_create.html', context)
            
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
                        return redirect('ai_config:training_file_edit', file_id=training_file.id)
                else:
                    if AITrainingFile.objects.filter(user=user, name=name).exists():
                        messages.error(request, 'Já existe um arquivo com este nome.')
                        os.remove(temp_file_path)
                        return render(request, 'training/file_create.html', {
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
                        return redirect('ai_config:training_file_edit', file_id=training_file.id)
                return redirect('ai_config:training_center')
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
    if active_capture and active_capture.is_active:
        active_capture.save()  # Atualiza last_activity
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
    
    return render(request, 'training/file_create.html', context)

@login_required
def training_file_download(request: HttpRequest, file_id: int) -> HttpResponse:
    """Permite o download de um arquivo de treinamento."""
    user = request.user
    training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
    response = FileResponse(training_file.file.open('rb'), as_attachment=True, filename=training_file.file.name)
    return response

@login_required
def training_file_delete(request: HttpRequest, file_id: int) -> HttpResponse:
    """Exclui um arquivo de treinamento."""
    user = request.user
    try:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        if request.method == 'POST':
            file_path = training_file.file.path
            training_file.file.delete()
            logger.debug(f"Arquivo físico deletado: {file_path}")
            training_file.delete()
            return JsonResponse({'success': True, 'message': 'Arquivo excluído com sucesso!'})
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    except Exception as e:
        logger.error(f"Erro ao excluir arquivo: {str(e)}")
        return JsonResponse({'error': 'Erro ao excluir arquivo'}, status=500)
