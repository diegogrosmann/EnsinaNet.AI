import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse

from accounts.models import UserToken
from ai_config.models import AIClientConfiguration
from ai_config.forms import AIClientConfigurationForm


logger = logging.getLogger(__name__)

@login_required
def ai_config_manage(request: HttpRequest, token_id: str) -> HttpResponse:
    """Exibe as configurações de IA associadas a um token.

    Args:
        request (HttpRequest): Requisição HTTP.
        token_id (str): Identificador do token.

    Returns:
        HttpResponse: Resposta renderizando a página de configurações.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_configs = AIClientConfiguration.objects.filter(token=token)
    context = {'token': token, 'ai_configs': ai_configs}
    return render(request, 'ai_config/manage.html', context)

@login_required
def ai_config_create(request: HttpRequest, token_id: str) -> HttpResponse:
    """Cria uma nova configuração de IA para um token.

    Args:
        request (HttpRequest): Requisição HTTP.
        token_id (str): Identificador do token.

    Returns:
        HttpResponse: Redireciona para a página de gerenciamento ou renderiza o formulário.
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
                return redirect('ai_config:ai_config_manage', token_id=token.id)
            except Exception as e:
                logger.exception("Erro ao salvar configuração de IA:")
                messages.error(request, f"Erro ao salvar: {e}")
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
    else:
        form = AIClientConfigurationForm()
    context = {'token': token, 'form': form}
    return render(request, 'ai_config/create.html', context)

@login_required
def ai_config_edit(request: HttpRequest, token_id: str, config_id: int) -> HttpResponse:
    """Edita uma configuração de IA existente."""
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_config = get_object_or_404(AIClientConfiguration, id=config_id, token=token)
    if request.method == 'POST':
        form = AIClientConfigurationForm(request.POST, instance=ai_config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração atualizada com sucesso!")
            return redirect('ai_config:ai_config_manage', token_id=token.id)
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
    else:
        form = AIClientConfigurationForm(instance=ai_config)
    
    context = {
        'token': token, 
        'form': form,
        'ai_config': ai_config,
        'is_edit': True  # Flag para identificar que é edição
    }
    return render(request, 'ai_config/create.html', context)

@login_required
def ai_config_delete(request: HttpRequest, token_id: str, config_id: int) -> HttpResponse:
    """Exclui uma configuração de IA.

    Args:
        request (HttpRequest): Requisição HTTP.
        token_id (str): Identificador do token.
        config_id (int): Identificador da configuração.

    Returns:
        HttpResponse: Resposta JSON para AJAX ou redirecionamento para requisições normais.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_config = get_object_or_404(AIClientConfiguration, id=config_id, token=token)

    if request.method == 'POST':
        try:
            name = ai_config.name
            ai_config.delete()
            
            # Verifica se é uma requisição AJAX
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'status': 'success',
                    'message': f"A configuração '{name}' foi deletada."
                })
            
            # Requisição normal (form submit)
            messages.success(request, f"A configuração '{name}' foi deletada.")
            return redirect('ai_config:ai_config_manage', token_id=token.id)
            
        except Exception as e:
            logger.exception("Erro ao deletar configuração de IA:")
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=500)
            
            messages.error(request, f"Erro ao deletar: {e}")
            return redirect('ai_config:ai_config_manage', token_id=token.id)

    # GET request - renderiza a página de gerenciamento
    return redirect('ai_config:ai_config_manage', token_id=token.id)


@login_required
def get_token_ais(request: HttpRequest, token_id: str) -> JsonResponse:
    """Retorna as configurações de IA disponíveis para um token específico.

    Args:
        request (HttpRequest): Requisição HTTP.
        token_id (str): ID do token.

    Returns:
        JsonResponse: Lista de configurações de IA do token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    
    ai_configs = AIClientConfiguration.objects.filter(token=token, enabled=True)
    ai_configs_data = [
        {
            'id': config.id,
            'name': config.name,
            'ai_client': config.ai_client.api_client_class
        }
        for config in ai_configs
    ]
    
    return JsonResponse({'ai_configs': ai_configs_data})

@login_required
def ai_config_toggle(request: HttpRequest, token_id: str, config_id: int) -> JsonResponse:
    """Alterna o status (enabled/disabled) de uma configuração de IA."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método não permitido'}, status=405)
    
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    ai_config = get_object_or_404(AIClientConfiguration, id=config_id, token=token)
    
    try:
        data = json.loads(request.body)
        ai_config.enabled = data.get('enabled', False)
        ai_config.save()
        return JsonResponse({
            'status': 'success',
            'message': f"IA {ai_config.name} {'ativada' if ai_config.enabled else 'desativada'} com sucesso"
        })
    except Exception as e:
        logger.exception("Erro ao alterar status da IA:")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
