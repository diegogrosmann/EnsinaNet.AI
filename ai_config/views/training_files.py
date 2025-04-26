<<<<<<< HEAD
"""
Views para gerenciamento de arquivos de treinamento.

Este módulo contém funções para criar, editar, fazer upload, baixar e excluir
arquivos de treinamento usados para treinar modelos de IA.

A documentação segue o padrão Google e os logs/exceções são tratados de forma padronizada.
"""

import logging
import uuid
import os
from typing import Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse, FileResponse
from django.forms import formset_factory
from django.conf import settings

from accounts.models import UserToken
from ai_config.models import AITrainingFile, TrainingCapture, AIClientConfiguration
from ai_config.forms import (
    AITrainingFileNameForm,
    TrainingCaptureForm,
    TrainingExampleForm
)
from core.types import APPResponse, APPError, AIExample, AIExampleDict

logger = logging.getLogger(__name__)


@login_required
def training_file_upload(request: HttpRequest) -> HttpResponse:
    """Processa o upload de um arquivo de treinamento.

    Recebe um arquivo JSON via upload, valida seu formato e o salva como arquivo de
    treinamento associado ao usuário atual.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Resposta JSON se via AJAX ou redirecionamento se não.
    """
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error = APPError(
                message="Método não suportado",
                code="method_not_allowed",
                status_code=405
            )
            response = APPResponse.create_failure(error)
            return JsonResponse(response.to_dict(), status=405)
        else:
            messages.error(request, 'Método não suportado!')
            return redirect('ai_config:training_center')
    try:
        if 'file' not in request.FILES:
            messages.error(request, "Nenhum arquivo enviado.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                error = APPError(
                    message="Nenhum arquivo enviado",
                    code="no_file",
                    status_code=400
                )
                response = APPResponse.create_failure(error)
                return JsonResponse(response.to_dict(), status=400)
            else:
                messages.error(request, 'Nenhum arquivo enviado!')
                return redirect('ai_config:training_center')
        uploaded_file = request.FILES['file']
        file_name = request.POST.get('name', uploaded_file.name)

        existing_file = AITrainingFile.objects.filter(user=request.user, name=file_name).first()
        if existing_file:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                error = APPError(
                    message="Já existe um arquivo com esse nome. Por favor, escolha outro.",
                    code="duplicate_file_name",
                    status_code=400
                )
                response = APPResponse.create_failure(error)
                return JsonResponse(response.to_dict(), status=400)
            else:
                messages.error(request, "Já existe um arquivo com esse nome. Por favor, escolha outro.")
                return redirect('ai_config:training_center')

        try:
            training_file = AITrainingFile.objects.create(
                user=request.user,
                name=file_name,
                file_data=uploaded_file.file
            )
            logger.info(f"Novo arquivo de treinamento criado: {file_name}")
            messages.success(request, f"Arquivo '{file_name}' criado com sucesso.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response_data = {
                    "message": f"Arquivo {file_name} criado com sucesso", 
                    "id": training_file.id
                }
                response = APPResponse.create_success(response_data)
                return JsonResponse(response.to_dict())
            else:
                return redirect('ai_config:training_center')
        except ValidationError as e:
            logger.error(f"Erro na validação do arquivo: {e}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                error = APPError(
                    message="Arquivo inválido",
                    code="invalid_file",
                    status_code=400
                )
                response = APPResponse.create_failure(error)
                return JsonResponse(response.to_dict(), status=400)
            else:
                messages.error(request, "Arquivo inválido!")
                return redirect('ai_config:training_center')
        except Exception as e:
            logger.error(f"Erro ao processar arquivo: {e}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                error = APPError(
                    message="Erro ao processar arquivo",
                    code="processing_error",
                    status_code=500,
                    error_id=str(uuid.uuid4())
                )
                response = APPResponse(success=False, error=error)
                return JsonResponse(response.to_dict(), status=500)
            else:
                messages.error(request, "Erro ao processar arquivo!")
                return redirect('ai_config:training_center')
    except Exception as e:
        logger.error(f"Erro ao processar upload de arquivo: {e}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error = APPError(
                message=f"Erro ao processar o arquivo: {e}",
                code="upload_error",
                status_code=500,
                error_id=str(uuid.uuid4())
            )
            response = APPResponse(success=False, error=error)
            return JsonResponse(response.to_dict(), status=500)
        else:
            return redirect('ai_config:training_center')


@login_required
def training_file_form(request: HttpRequest, file_id: Optional[int] = None) -> HttpResponse:
    """Cria ou edita um arquivo de treinamento usando o editor web.

    Permite criar um novo arquivo de treinamento ou editar um existente
    utilizando a interface web com formulários para exemplos.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        file_id (Optional[int]): ID opcional do arquivo de treinamento a ser editado.

    Returns:
        HttpResponse: Página renderizada ou redirecionamento.
    """
    training_file = None
    initial_examples = []

    if file_id:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=request.user)
        try:
            examples = training_file.file_data
            # Convertendo os exemplos para uma lista de dicionários compatível com o formset
            initial_examples = []
            if examples and hasattr(examples, 'items'):
                for example_id, example in examples.items():
                    if hasattr(example, 'to_dict'):
                        example_dict = example.to_dict()
                        initial_examples.append({
                            'system_message': example_dict.get('system_message', ''),
                            'user_message': example_dict.get('user_message', ''),
                            'response': example_dict.get('response', '')
                        })
                    else:
                        # Caso o exemplo não tenha método to_dict
                        initial_examples.append({
                            'system_message': getattr(example, 'system_message', ''),
                            'user_message': getattr(example, 'user_message', ''),
                            'response': getattr(example, 'response', '')
                        })
            logger.debug(f"Carregados {len(initial_examples)} exemplos para o editor")
        except Exception as e:
            logger.error(f"Erro ao carregar dados do arquivo {file_id}: {e}", exc_info=True)
            messages.error(request, f"Erro ao carregar o arquivo: {e}")
            return redirect('ai_config:training_center')

    formset_class = formset_factory(TrainingExampleForm, can_delete=True, extra=0 if file_id else 1)

    if request.method == 'POST':
        name_form = AITrainingFileNameForm(request.POST, prefix='name')
        example_formset = formset_class(request.POST, prefix='form')
        if name_form.is_valid() and example_formset.is_valid():
            try:
                examples = []
                for form in example_formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                        examples.append(AIExample(
                            system_message=form.cleaned_data.get('system_message', ''),
                            user_message=form.cleaned_data.get('user_message'),
                            response=form.cleaned_data.get('response')
                        ))
                new_name = name_form.cleaned_data['name']
                temp_training_files = AITrainingFile.objects.filter(user=request.user, name=new_name)

                if training_file:
                    if temp_training_files.exclude(id=training_file.id).exists():
                        messages.error(request, "Já existe outro arquivo com esse nome. Escolha outro nome.")
                        return render(request, 'training/file_form.html', {
                            'name_form': name_form,
                            'formset': example_formset,
                            'training_file': training_file,
                            'active_capture': TrainingCapture.objects.filter(token__user=request.user, is_active=True).first(),
                            'capture_form': TrainingCaptureForm(user=request.user)
                        })
                    training_file.name = new_name
                    
                    # Cria um AIExampleDict a partir da lista de exemplos
                    example_dict = AIExampleDict()
                    for i, example in enumerate(examples):
                        example_dict.put_item(str(i), example)
                    
                    training_file.file_data = example_dict
                    training_file.save()
                    messages.success(request, f"Arquivo '{training_file.name}' atualizado com sucesso.")
                else:
                    if temp_training_files.exists():
                        messages.error(request, "Já existe um arquivo com esse nome. Escolha outro nome.")
                        return render(request, 'training/file_form.html', {
                            'name_form': name_form,
                            'formset': example_formset,
                            'training_file': None,
                            'active_capture': TrainingCapture.objects.filter(token__user=request.user, is_active=True).first(),
                            'capture_form': TrainingCaptureForm(user=request.user)
                        })
                    
                    # Cria um AIExampleDict a partir da lista de exemplos
                    example_dict = AIExampleDict()
                    for i, example in enumerate(examples):
                        example_dict.put_item(str(i), example)
                    
                    training_file = AITrainingFile.objects.create(
                        user=request.user,
                        name=new_name,
                        file_data=example_dict
                    )
                    logger.info(f"Novo arquivo de treinamento criado: {new_name}")
                    messages.success(request, f"Arquivo '{new_name}' criado com sucesso.")
                if 'save_and_continue' in request.POST:
                    return redirect('ai_config:training_file_edit', file_id=training_file.id)
                else:
                    return redirect('ai_config:training_center')
            except Exception as e:
                logger.error(f"Erro ao salvar arquivo de treinamento: {e}", exc_info=True)
                messages.error(request, f"Erro ao salvar arquivo: {e}")
        else:
            logger.warning(f"Formulário inválido: {name_form.errors} | {example_formset.errors}")
    else:
        name_form = AITrainingFileNameForm(initial={'name': training_file.name} if file_id else None, prefix='name')
        example_formset = formset_class(initial=initial_examples, prefix='form')

    return render(request, 'training/file_form.html', {
        'name_form': name_form,
        'formset': example_formset,
        'training_file': training_file,
        'active_capture': TrainingCapture.objects.filter(token__user=request.user, is_active=True).first(),
        'capture_form': TrainingCaptureForm(user=request.user)
    })


@login_required
def training_file_download(request: HttpRequest, file_id: int) -> HttpResponse:
    """Permite o download de um arquivo de treinamento.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        file_id (int): ID do arquivo de treinamento.

    Returns:
        HttpResponse: Resposta com o arquivo para download.
    """
    try:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=request.user)
        filename = f"{training_file.name}.json"
        file_path = training_file.get_full_path()
        if not os.path.exists(file_path):
            logger.error(f"Arquivo físico não encontrado: {file_path}")
            messages.error(request, "Arquivo não encontrado no servidor.")
            return redirect('ai_config:training_center')
        response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)
        response['X-No-Transition-Loader'] = 'true'
        logger.info(f"Download do arquivo {file_id} realizado pelo usuário {request.user.id}")
        return response
    except Exception as e:
        logger.error(f"Erro ao processar download do arquivo {file_id}: {e}", exc_info=True)
        messages.error(request, f"Erro ao baixar arquivo: {e}")
        return redirect('ai_config:training_center')


@login_required
def training_file_delete(request: HttpRequest, file_id: int) -> HttpResponse:
    """Exclui um arquivo de treinamento.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        file_id (int): ID do arquivo de treinamento.

    Returns:
        HttpResponse: Redirecionamento ou resposta JSON.
    """
    if request.method not in ['POST', 'DELETE']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error = APPError(
                message="Método não suportado",
                code="method_not_allowed",
                status_code=405
            )
            response = APPResponse(success=False, error=error)
            return JsonResponse(response.to_dict(), status=405)
        else:
            messages.error(request, "Método não suportado")
            return redirect('ai_config:training_center')
    try:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=request.user)
        file_name = training_file.name
        training_file.delete()
        logger.info(f"Arquivo de treinamento {file_id} excluído pelo usuário {request.user.id}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response_data = {"message": f"Arquivo '{file_name}' excluído com sucesso"}
            response = APPResponse(success=True, data=response_data)
            return JsonResponse(response.to_dict())
        else:
            messages.success(request, f"Arquivo '{file_name}' excluído com sucesso.")
            return redirect('ai_config:training_center')
    except Exception as e:
        logger.error(f"Erro ao excluir arquivo de treinamento: {e}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error = APPError(
                message=f"Erro ao excluir arquivo: {e}",
                code="delete_error",
                status_code=500,
                error_id=str(uuid.uuid4())
            )
            response = APPResponse(success=False, error=error)
            return JsonResponse(response.to_dict(), status=500)
        else:
            messages.error(request, f"Erro ao excluir arquivo: {e}")
            return redirect('ai_config:training_center')


@login_required
def capture_toggle(request: HttpRequest) -> JsonResponse:
    """Ativa ou desativa a captura de exemplos de treinamento.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        JsonResponse: Status da operação.
    """
    if request.method != 'POST':
        error = APPError(
            message="Método não suportado",
            code="method_not_allowed",
            status_code=405
        )
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=405)
        
    action = request.POST.get('action')
    if action == 'activate':
        token_id = request.POST.get('token')
        ai_config_id = request.POST.get('ai_client_config')
        if not token_id or not ai_config_id:
            error = APPError(
                message="Token e configuração de IA são obrigatórios",
                code="missing_required_fields",
                status_code=400
            )
            response = APPResponse(success=False, error=error)
            return JsonResponse(response.to_dict(), status=400)
            
        try:
            token = get_object_or_404(UserToken, id=token_id, user=request.user)
            ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id, user=request.user)
            
            TrainingCapture.objects.filter(token__user=request.user, is_active=True).update(is_active=False)
            capture, created = TrainingCapture.objects.get_or_create(
                token=token,
                defaults={'ai_client_config': ai_config, 'is_active': True}
            )
            if not created:
                capture.ai_client_config = ai_config
                capture.is_active = True
                capture.save()
                
            response_data = {"message": "Captura ativada com sucesso"}
            response = APPResponse(success=True, data=response_data)
            return JsonResponse(response.to_dict())
        except Exception as e:
            logger.error(f"Erro ao ativar captura: {e}", exc_info=True)
            error = APPError(
                message=f"Erro ao ativar captura: {e}",
                code="activation_error",
                status_code=500,
                error_id=str(uuid.uuid4())
            )
            response = APPResponse(success=False, error=error)
            return JsonResponse(response.to_dict(), status=500)
    else:
        # Desativar a captura
        try:
            captures = TrainingCapture.objects.filter(token__user=request.user, is_active=True)
            for capture in captures:
                capture.is_active = False
                capture.save()
            
            response_data = {"message": "Captura desativada com sucesso"}
            response = APPResponse(success=True, data=response_data)
            return JsonResponse(response.to_dict())
        except Exception as e:
            logger.error(f"Erro ao desativar captura: {e}", exc_info=True)
            error = APPError(
                message=f"Erro ao desativar captura: {e}",
                code="deactivation_error",
                status_code=500,
                error_id=str(uuid.uuid4())
            )
            response = APPResponse(success=False, error=error)
            return JsonResponse(response.to_dict(), status=500)


@login_required
def capture_get_examples(request: HttpRequest, token_id: uuid.UUID, ai_id: int) -> JsonResponse:
    """Obtém os exemplos capturados para um token e IA específicos.

    Coleta os exemplos do arquivo temporário da captura e limpa a coleção após a leitura.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        token_id (uuid.UUID): ID do token.
        ai_id (int): ID da configuração da IA.

    Returns:
        JsonResponse: Lista de exemplos capturados ou mensagem de erro.
    """
    if request.method != 'GET':
        error = APPError(
            message="Método não suportado",
            code="method_not_allowed",
            status_code=405
        )
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=405)
        
    try:
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        try:
            capture = TrainingCapture.objects.get(token=token, ai_client_config=ai_config)
            collection = capture.file_data
            # Limpa a coleção após leitura
            capture.file_data = AIExampleDict()
            capture.save()
            logger.info(f"Retornados {len(collection.examples)} exemplos para token {token.name}")
            
            response_data = {
                "examples": collection.to_dict(), 
                "count": len(collection.examples)
            }
            response = APPResponse(success=True, data=response_data)
            return JsonResponse(response.to_dict())
        except TrainingCapture.DoesNotExist:
            response_data = {
                "examples": [], 
                "count": 0, 
                "message": "Não há captura configurada para este token."
            }
            response = APPResponse(success=True, data=response_data)
            return JsonResponse(response.to_dict())
    except UserToken.DoesNotExist:
        error = APPError(
            message='Token não encontrado',
            code='token_not_found',
            status_code=404
        )
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=404)
    except AIClientConfiguration.DoesNotExist:
        error = APPError(
            message='Configuração de IA não encontrada',
            code='ai_config_not_found',
            status_code=404
        )
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        logger.exception(f"Erro ao obter exemplos capturados: {e}")
        error = APPError(
            message=str(e),
            code='example_retrieval_error',
            status_code=500,
            error_id=str(uuid.uuid4())
        )
        response = APPResponse(success=False, error=error)
        return JsonResponse(response.to_dict(), status=500)
=======
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
    """Exibe a confirmação e processa a exclusão de um arquivo de treinamento."""
    user = request.user
    training_file = get_object_or_404(AITrainingFile, id=file_id, user=user)
    if request.method == 'POST':
        file_path = training_file.file.path
        training_file.file.delete()
        logger.debug(f"Arquivo físico deletado: {file_path}")
        training_file.delete()
        messages.success(request, 'Arquivo excluído com sucesso!')
        return redirect('ai_config:training_center')
    context = {'training_file': training_file}
    return render(request, 'training/file_confirm_delete.html', context)
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
