"""
Views para gerenciamento de arquivos de treinamento.

Este módulo contém funções para criar, editar, fazer upload, baixar e excluir
arquivos de treinamento usados para treinar modelos de IA.
"""

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
from django.db import transaction

from core.validators import validate_training_file
from accounts.models import UserToken
from ai_config.models import AITrainingFile, TrainingCapture, AIClientGlobalConfiguration
from ai_config.forms import (
    TrainingExampleForm,
    AITrainingFileNameForm,
    TrainingCaptureForm
)

logger = logging.getLogger(__name__)

@login_required
def training_file_upload(request: HttpRequest) -> JsonResponse:
    """Processa o upload de um arquivo de treinamento.
    
    Recebe um arquivo JSON via upload, valida seu formato e o salva como
    arquivo de treinamento associado ao usuário atual.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        JsonResponse: Resposta JSON com status da operação.
    """
    if request.method != 'POST':
        logger.warning(f"Tentativa de acessar upload com método inválido: {request.method}")
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        user = request.user
        name = request.POST.get('name')
        file = request.FILES.get('file')

        logger.debug(f"Iniciando upload de arquivo de treinamento: '{name}' por {user.email}")

        if not file or not name:
            logger.warning(f"Upload de arquivo sem nome ou arquivo: nome={bool(name)}, arquivo={bool(file)}")
            return JsonResponse({
                'error': 'Nome do arquivo e arquivo são obrigatórios'
            }, status=400)

        # Valida o formato do arquivo
        is_valid, error_message, _ = validate_training_file(file)
        if not is_valid:
            return JsonResponse({'error': error_message}, status=400)

        # Gera um nome único para o arquivo
        extension = file.name.split('.')[-1] if '.' in file.name else ''
        unique_filename = f"{uuid.uuid4().hex[:8]}_{name}.{extension}"
        file.name = unique_filename

        # Verifica se já existe um arquivo com este nome
        if AITrainingFile.objects.filter(user=user, name=name).exists():
            logger.warning(f"Tentativa de criar arquivo com nome duplicado: '{name}' por {user.email}")
            return JsonResponse({
                'error': 'Já existe um arquivo com este nome'
            }, status=400)

        # Cria novo arquivo de treinamento
        with transaction.atomic():
            training_file = AITrainingFile(
                user=user,
                name=name,
                file=file
            )
            training_file.save()

        logger.info(f"Arquivo de treinamento '{name}' (ID: {training_file.id}) enviado com sucesso por {user.email}")
        return JsonResponse({
            'success': True,
            'message': 'Arquivo enviado com sucesso',
            'id': training_file.id,
            'name': training_file.name
        })
        
    except Exception as e:
        logger.exception(f"Erro no upload do arquivo de treinamento: {str(e)}")
        return JsonResponse({
            'error': 'Erro ao processar o upload do arquivo'
        }, status=500)

@login_required
def training_file_create(request: HttpRequest, file_id: Optional[int] = None) -> HttpResponse:
    """Cria ou edita um arquivo de treinamento usando o editor web.
    
    Permite criar um novo arquivo de treinamento ou editar um existente
    usando a interface web com formulários para exemplos.
    
    Args:
        request: Objeto de requisição HTTP.
        file_id: ID opcional do arquivo de treinamento a ser editado.
        
    Returns:
        HttpResponse: Página renderizada ou redirecionamento.
    """
    user = request.user
    training_file = None
    initial_data = []
    initial_name = ''
    
    try:
        # Se file_id for fornecido, estamos editando um arquivo existente
        if file_id:
            training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
            initial_name = training_file.name
            logger.debug(f"Editando arquivo de treinamento existente: '{initial_name}' (ID: {file_id})")
            
            try:
                with training_file.file.open('r') as f:
                    is_valid, error_message, data = validate_training_file(f)
                    if not is_valid:
                        logger.warning(f"Arquivo '{initial_name}' com formato inválido: {error_message}")
                        messages.error(request, f'Arquivo inválido: {error_message}')
                        return redirect('ai_config:training_center')
                    initial_data = data
            except Exception as e:
                logger.exception(f"Erro ao abrir arquivo de treinamento '{initial_name}' (ID: {file_id}): {e}")
                messages.error(request, 'Erro ao abrir arquivo.')
                return redirect('ai_config:training_center')
        else:
            logger.debug(f"Criando novo arquivo de treinamento para {user.email}")
        
        # Configura os formulários necessários
        formset_class = formset_factory(TrainingExampleForm, can_delete=True, extra=0 if file_id else 1)
        name_form = AITrainingFileNameForm(initial={'name': initial_name} if file_id else None, prefix='name')
        formset = formset_class(initial=initial_data, prefix='form')
        
        # Processar submissão do formulário
        if request.method == 'POST':
            name_form = AITrainingFileNameForm(request.POST, prefix='name')
            formset = formset_class(request.POST, prefix='form')
            
            if name_form.is_valid() and formset.is_valid():
                name = name_form.cleaned_data['name']
                examples = []
                
                # Processar exemplos do formulário
                for form in formset:
                    if form.is_valid() and form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                        examples.append({
                            'system_message': form.cleaned_data.get('system_message', '').strip(),
                            'user_message': form.cleaned_data.get('user_message', '').strip(),
                            'response': form.cleaned_data.get('response', '').strip()
                        })
                
                # Validar que há pelo menos um exemplo
                if not examples:
                    logger.warning(f"Tentativa de salvar arquivo de treinamento sem exemplos: '{name}'")
                    messages.error(request, 'Adicione pelo menos um exemplo.')
                    context = {
                        'formset': formset,
                        'name_form': name_form,
                        'capture_form': TrainingCaptureForm(prefix='capture', user=user)
                    }
                    return render(request, 'training/file_form.html', context)
                
                # Criar arquivo temporário com os exemplos
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as temp_file:
                    json.dump(examples, temp_file, ensure_ascii=False, indent=4)
                    temp_file_path = temp_file.name
                
                try:
                    if training_file:
                        # Atualizar arquivo existente
                        existing_file_name = os.path.basename(training_file.file.name)
                        with open(temp_file_path, 'rb') as f:
                            training_file.file.save(existing_file_name, File(f), save=True)
                        
                        if training_file.name != name:
                            training_file.name = name
                            training_file.save()
                            
                        logger.info(f"Arquivo de treinamento '{name}' (ID: {file_id}) atualizado por {user.email}")
                        messages.success(request, 'Arquivo atualizado com sucesso!')
                        
                        if 'save_and_continue' in request.POST:
                            return redirect('ai_config:training_file_edit', file_id=training_file.id)
                    else:
                        # Verificar se já existe um arquivo com este nome
                        if AITrainingFile.objects.filter(user=user, name=name).exists():
                            logger.warning(f"Tentativa de criar arquivo com nome duplicado: '{name}' por {user.email}")
                            messages.error(request, 'Já existe um arquivo com este nome.')
                            os.remove(temp_file_path)
                            return render(request, 'training/file_form.html', {
                                'formset': formset,
                                'name_form': name_form,
                                'capture_form': TrainingCaptureForm(prefix='capture', user=user)
                            })
                        
                        # Criar novo arquivo
                        unique_filename = f"{name}_{uuid.uuid4().hex}.json"
                        with open(temp_file_path, 'rb') as f:
                            with transaction.atomic():
                                training_file = AITrainingFile.objects.create(
                                    user=user,
                                    name=name,
                                    file=File(f, name=unique_filename)
                                )
                        
                        logger.info(f"Novo arquivo de treinamento '{name}' (ID: {training_file.id}) criado por {user.email}")
                        messages.success(request, 'Arquivo criado com sucesso!')
                        
                        if 'save_and_continue' in request.POST:
                            return redirect('ai_config:training_file_edit', file_id=training_file.id)
                    
                    return redirect('ai_config:training_center')
                except Exception as e:
                    logger.exception(f"Erro ao salvar arquivo de treinamento '{name}': {e}")
                    messages.error(request, f'Erro ao salvar arquivo: {str(e)}')
                finally:
                    # Limpeza do arquivo temporário
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
            else:
                if not name_form.is_valid():
                    logger.warning(f"Formulário de nome inválido: {name_form.errors}")
                    messages.error(request, 'Corrija os erros no campo de nome.')
                if not formset.is_valid():
                    logger.warning(f"Formulário de exemplos inválido")
                    messages.error(request, 'Corrija os erros nos exemplos.')
        
        # Configuração da captura ativa
        active_capture = TrainingCapture.objects.filter(token__user=user, is_active=True).first()
        if active_capture and active_capture.is_active:
            active_capture.save()  # Atualiza last_activity
            capture_form = TrainingCaptureForm(instance=active_capture, prefix='capture', user=user)
            logger.debug(f"Captura ativa encontrada para {user.email}")
        else:
            capture_form = TrainingCaptureForm(prefix='capture', user=user)
        
        context = {
            'formset': formset,
            'name_form': name_form,
            'training_file': training_file,
            'capture_form': capture_form,
            'active_capture': active_capture,
        }
        
        return render(request, 'training/file_form.html', context)
    except Exception as e:
        logger.exception(f"Erro ao processar criação/edição de arquivo de treinamento: {e}")
        messages.error(request, f'Ocorreu um erro: {str(e)}')
        return redirect('ai_config:training_center')

@login_required
def training_file_download(request: HttpRequest, file_id: int) -> HttpResponse:
    """Permite o download de um arquivo de treinamento.
    
    Args:
        request: Objeto de requisição HTTP.
        file_id: ID do arquivo de treinamento.
        
    Returns:
        HttpResponse: Resposta com o arquivo para download.
    """
    user = request.user
    try:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        logger.info(f"Download do arquivo '{training_file.name}' (ID: {file_id}) por {user.email}")
        
        # Criar nome do arquivo para download (usar apenas o nome original sem o UUID)
        filename = f"{training_file.name}.json"
        
        response = FileResponse(
            training_file.file.open('rb'), 
            as_attachment=True, 
            filename=filename
        )
        return response
    except AITrainingFile.DoesNotExist:
        logger.warning(f"Tentativa de download de arquivo inexistente (ID: {file_id}) por {user.email}")
        messages.error(request, 'Arquivo não encontrado.')
        return redirect('ai_config:training_center')
    except Exception as e:
        logger.exception(f"Erro ao fazer download do arquivo {file_id}: {e}")
        messages.error(request, f'Erro ao baixar arquivo: {str(e)}')
        return redirect('ai_config:training_center')

@login_required
def training_file_delete(request: HttpRequest, file_id: int) -> HttpResponse:
    """Exclui um arquivo de treinamento.
    
    Args:
        request: Objeto de requisição HTTP.
        file_id: ID do arquivo de treinamento.
        
    Returns:
        JsonResponse: Resposta JSON com status da operação.
    """
    user = request.user
    
    if request.method != 'POST':
        logger.warning(f"Tentativa de exclusão com método não permitido: {request.method}")
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
        file_name = training_file.name
        
        try:
            # Salvar caminho do arquivo antes de deletar o modelo
            file_path = training_file.file.path if training_file.file else None
            
            with transaction.atomic():
                # Excluir o arquivo físico primeiro
                if file_path and os.path.exists(file_path):
                    training_file.file.delete()
                    logger.debug(f"Arquivo físico deletado: {file_path}")
                
                # Em seguida, excluir o registro do banco de dados
                training_file.delete()
            
            logger.info(f"Arquivo de treinamento '{file_name}' (ID: {file_id}) excluído por {user.email}")
            messages.success(request, 'Arquivo excluído com sucesso!')
            return JsonResponse({'success': True, 'message': 'Arquivo excluído com sucesso!'})
        except Exception as e:
            logger.exception(f"Erro ao excluir arquivo '{file_name}' (ID: {file_id}): {e}")
            return JsonResponse({'error': f'Erro ao excluir arquivo: {str(e)}'}, status=500)
    except AITrainingFile.DoesNotExist:
        logger.warning(f"Tentativa de exclusão de arquivo inexistente (ID: {file_id}) por {user.email}")
        return JsonResponse({'error': 'Arquivo não encontrado.'}, status=404)
    except Exception as e:
        logger.exception(f"Erro ao processar exclusão do arquivo {file_id}: {e}")
        return JsonResponse({'error': f'Erro ao excluir arquivo: {str(e)}'}, status=500)
