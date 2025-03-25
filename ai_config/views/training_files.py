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
from core.types import APIResponse
from core.types.training import (
    AITrainingExample,
    AITrainingExampleCollection
)

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
            return JsonResponse(APIResponse.error_response(error_message="Método não suportado").to_dict())
        else:
            messages.error(request, 'Método não suportado!')
            return redirect('ai_config:training_center')
    try:
        if 'file' not in request.FILES:
            messages.error(request, "Nenhum arquivo enviado.")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(APIResponse.error_response(error_message="Nenhum arquivo enviado").to_dict())
            else:
                messages.error(request, 'Nenhum arquivo enviado!')
                return redirect('ai_config:training_center')
        uploaded_file = request.FILES['file']
        file_name = request.POST.get('name', uploaded_file.name)

        existing_file = AITrainingFile.objects.filter(user=request.user, name=file_name).first()
        if existing_file:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(APIResponse.error_response(error_message="Já existe um arquivo com esse nome. Por favor, escolha outro.").to_dict())
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
                return JsonResponse(APIResponse.success_response(data={"message": f"Arquivo {file_name} criado com sucesso", "id": training_file.id}).to_dict())
            else:
                return redirect('ai_config:training_center')
        except ValidationError as e:
            logger.error(f"Erro na validação do arquivo: {e}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(APIResponse.error_response(error_message="Arquivo inválido.").to_dict())
            else:
                messages.error(request, "Arquivo inválido!")
                return redirect('ai_config:training_center')
        except Exception as e:
            logger.error(f"Erro ao processar arquivo: {e}", exc_info=True)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(APIResponse.error_response(error_message="Erro ao processar arquivo.").to_dict())
            else:
                messages.error(request, "Erro ao processar arquivo!")
                return redirect('ai_config:training_center')
    except Exception as e:
        logger.error(f"Erro ao processar upload de arquivo: {e}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(APIResponse.error_response(error_message=f"Erro ao processar o arquivo: {e}").to_dict())
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
            initial_examples = examples.to_dict()
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
                        examples.append(AITrainingExample(
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
                    training_file.file_data.examples = examples
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
                    training_file = AITrainingFile.objects.create(
                        user=request.user,
                        name=new_name,
                        file_data=AITrainingExampleCollection(examples=examples)
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
            return JsonResponse(APIResponse.error_response(error_message="Método não suportado").to_dict())
        else:
            messages.error(request, "Método não suportado")
            return redirect('ai_config:training_center')
    try:
        training_file = get_object_or_404(AITrainingFile, id=file_id, user=request.user)
        file_name = training_file.name
        training_file.delete()
        logger.info(f"Arquivo de treinamento {file_id} excluído pelo usuário {request.user.id}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(APIResponse.success_response(data={"message": f"Arquivo '{file_name}' excluído com sucesso"}).to_dict())
        else:
            messages.success(request, f"Arquivo '{file_name}' excluído com sucesso.")
            return redirect('ai_config:training_center')
    except Exception as e:
        logger.error(f"Erro ao excluir arquivo de treinamento: {e}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(APIResponse.error_response(error_message=f"Erro ao excluir arquivo: {e}").to_dict())
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
        return JsonResponse(APIResponse.error_response(error_message="Método não suportado").to_dict())
    action = request.POST.get('action')
    if action == 'activate':
        token_id = request.POST.get('token')
        ai_config_id = request.POST.get('ai_client_config')
        if not token_id or not ai_config_id:
            return JsonResponse(APIResponse.error_response(error_message="Token e configuração de IA são obrigatórios").to_dict(), status=400)
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
            return JsonResponse(APIResponse.success_response(data={"message": "Captura desativada com sucesso"}).to_dict())
        except Exception as e:
            logger.error(f"Erro ao desativar captura: {e}", exc_info=True)
            return JsonResponse(APIResponse.error_response(error_message=f"Erro ao desativar captura: {e}").to_dict(), status=500)
    else:
        return JsonResponse(APIResponse.error_response(error_message="Ação inválida").to_dict())


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
        return JsonResponse(APIResponse.error_response(error_message="Método não suportado").to_dict())
    try:
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        try:
            capture = TrainingCapture.objects.get(token=token, ai_client_config=ai_config)
            collection = capture.file_data
            # Limpa a coleção após leitura
            capture.file_data = AITrainingExampleCollection()
            capture.save()
            logger.info(f"Retornados {len(collection.examples)} exemplos para token {token.name}")
            response = APIResponse.success_response(data={"examples": collection.to_dict(), "count": len(collection.examples)})
            return JsonResponse(response.to_dict())
        except TrainingCapture.DoesNotExist:
            response = APIResponse.success_response(data={"examples": [], "count": 0, "message": "Não há captura configurada para este token."})
            return JsonResponse(response.to_dict())
    except UserToken.DoesNotExist:
        response = APIResponse.error_response(error_message='Token não encontrado.')
        return JsonResponse(response.to_dict(), status=404)
    except AIClientConfiguration.DoesNotExist:
        response = APIResponse.error_response(error_message='Configuração de IA não encontrada.')
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        logger.exception(f"Erro ao obter exemplos capturados: {e}")
        response = APIResponse.error_response(error_message=str(e))
        return JsonResponse(response.to_dict(), status=500)
