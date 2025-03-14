"""
Views para configuração de tokens e prompts.

Este módulo contém funções para gerenciar configurações de prompt
e vinculação de tokens com clientes de IA.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db import transaction

from accounts.models import UserToken
from ai_config.models import TokenAIConfiguration, AIClientConfiguration, AIClientTokenConfig
from ai_config.forms import TokenAIConfigurationForm

logger = logging.getLogger(__name__)

@login_required
def prompt_config(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia as configurações de prompt para o token.

    Permite definir instruções base, prompts e respostas personalizadas
    para um token específico.

    Args:
        request: Requisição HTTP.
        token_id: Identificador do token.

    Returns:
        HttpResponse: Página com o formulário das configurações do token.
    """
    user = request.user
    try:
        token = get_object_or_404(UserToken, id=token_id, user=user)
        token_ai_config, created = TokenAIConfiguration.objects.get_or_create(token=token)
        
        if created:
            logger.info(f"Nova configuração TokenAI criada para token '{token.name}' (ID: {token_id})")
        
        if request.method == 'POST':
            form = TokenAIConfigurationForm(request.POST, request.FILES, instance=token_ai_config, user=user)
            if form.is_valid():
                # Validação adicional do prompt
                prompt = form.cleaned_data.get('prompt', '').strip()
                if not prompt:
                    logger.warning(f"Tentativa de salvar configuração TokenAI sem prompt para token {token_id}")
                    form.add_error('prompt', 'Este campo é obrigatório.')
                    messages.error(request, 'O campo Prompt é obrigatório.')
                else:
                    try:
                        with transaction.atomic():
                            form.save()
                            
                        logger.info(f"Configurações TokenAI atualizadas para token '{token.name}' (ID: {token_id})")
                        
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'status': 'success', 'message': 'Configurações salvas com sucesso!'})
                        
                        messages.success(request, 'Configurações TokenAI atualizadas com sucesso!')
                        return redirect('accounts:token_config', token_id=token.id)
                    except Exception as e:
                        logger.exception(f"Erro ao salvar TokenAIConfiguration para token {token_id}: {e}")
                        messages.error(request, f'Erro ao salvar as configurações TokenAI: {str(e)}')
            else:
                logger.warning(f"Formulário TokenAI inválido para token {token_id}: {form.errors}")
                if 'prompt' in form.errors:
                    messages.error(request, 'O campo Prompt é obrigatório.')
                else:
                    messages.error(request, 'Corrija os erros no formulário TokenAI.')
        else:
            form = TokenAIConfigurationForm(instance=token_ai_config, user=user)
            logger.debug(f"Exibindo configuração TokenAI para token '{token.name}' (ID: {token_id})")
        
        context = {'token': token, 'form': form}
        return render(request, 'token/prompt_config.html', context)
    except UserToken.DoesNotExist:
        logger.warning(f"Tentativa de acessar configuração TokenAI para token inexistente: {token_id}")
        messages.error(request, 'Token não encontrado.')
        return redirect('accounts:tokens_manage')
    except Exception as e:
        logger.exception(f"Erro ao acessar configuração TokenAI para token {token_id}: {e}")
        messages.error(request, 'Ocorreu um erro ao carregar a configuração. Tente novamente mais tarde.')
        return redirect('accounts:tokens_manage')

@login_required
def token_ai_link(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia a vinculação e ativação de IAs ao token.

    Permite vincular várias IAs a um token e ativá-las/desativá-las.
    Suporta operações em massa e toggles individuais via AJAX.

    Args:
        request: Requisição HTTP.
        token_id: Identificador do token.

    Returns:
        HttpResponse: Página com lista de IAs disponíveis para o token.
    """
    user = request.user
    try:
        token = get_object_or_404(UserToken, id=token_id, user=user)
        logger.debug(f"Acessando configurações de vínculo para token '{token.name}' (ID: {token_id})")
        
        # Obter todas as configurações de IA do usuário
        user_ai_configs = AIClientConfiguration.objects.filter(user=user)
        
        # Obter as configurações já vinculadas a este token
        linked_config_ids = {config.ai_config_id for config in AIClientTokenConfig.objects.filter(token=token)}
        enabled_config_ids = {
            config.ai_config_id 
            for config in AIClientTokenConfig.objects.filter(token=token, enabled=True)
        }
        
        # Extrair lista de clientes de API únicos para o filtro
        unique_clients = {}
        for config in user_ai_configs:
            client_name = config.ai_client
            client_id = str(config.ai_client.id)
            if client_id not in unique_clients:
                unique_clients[client_id] = client_name
        
        if request.method == 'POST':
            # Processar as alterações nas vinculações - com suporte para AJAX single toggle
            enabled_ais = request.POST.getlist('enabled_ai')
            disable_ais = request.POST.getlist('disable_ai')
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            try:
                
                with transaction.atomic():
                    # Para requisições AJAX de um único toggle
                    if is_ajax:
                        # Identificar a IA que está sendo manipulada
                        toggled_ai_id = None
                        
                        # Verificar se temos uma IA no ai_configs (caso de ativação)
                        for enabled_ai in enabled_ais:
                            # Atualizar ou criar a configuração
                            AIClientTokenConfig.objects.update_or_create(
                                token=token,
                                ai_config_id=enabled_ai,
                                defaults={'enabled': True}
                            )
                            logger.info(f"IA {enabled_ai} ativada para token '{token.name}'")

                        for disable_ai in disable_ais:
                            # Desativar a configuração
                            AIClientTokenConfig.objects.update_or_create(
                                token=token,
                                ai_config_id=disable_ai,
                                defaults={'enabled': False}
                            )
                            logger.info(f"IA {toggled_ai_id} desativada para token '{token.name}'")
                    
                        return JsonResponse({'status': 'success'})
                    
            except ValueError as e:
                logger.error(f"Erro de validação ao atualizar vinculações para token {token_id}: {e}")
                if not is_ajax:
                    messages.error(request, 'Formato de dados inválido.')
                    return redirect('ai_config:token_ai_link', token_id=token.id)
                else:
                    return JsonResponse({'status': 'error', 'message': 'Formato de dados inválido'}, status=400)
            except Exception as e:
                logger.exception(f"Erro ao atualizar vinculações de IA para token {token_id}: {e}")
                if not is_ajax:
                    messages.error(request, 'Ocorreu um erro ao salvar as vinculações de IA.')
                    return redirect('ai_config:token_ai_link', token_id=token.id)
                else:
                    return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        
        context = {
            'token': token,
            'ai_configs': user_ai_configs,
            'linked_config_ids': linked_config_ids,
            'enabled_config_ids': enabled_config_ids,
            'unique_clients': unique_clients
        }
        
        return render(request, 'token/ai_link.html', context)
    except UserToken.DoesNotExist:
        logger.warning(f"Tentativa de acessar vinculação de IA para token inexistente: {token_id}")
        messages.error(request, 'Token não encontrado.')
        return redirect('accounts:tokens_manage')
    except Exception as e:
        logger.exception(f"Erro ao acessar vinculação de IA para token {token_id}: {e}")
        messages.error(request, 'Ocorreu um erro ao carregar as configurações de vinculação.')
        return redirect('accounts:tokens_manage')
