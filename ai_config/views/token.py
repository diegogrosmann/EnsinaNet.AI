"""
Views para configuração de tokens e prompts.

Este módulo contém funções para gerenciar configurações de prompt
e vinculação de tokens com clientes de IA.
"""

import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db import transaction

from accounts.models import UserToken
from ai_config.models import TokenAIConfiguration, AIClientConfiguration, AIClientTokenConfig
from ai_config.forms import TokenAIConfigurationForm
from core.types import APPResponse

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
                            response = APPResponse(
                                success=True,
                                data={'message': 'Configurações salvas com sucesso!'}
                            )
                            return JsonResponse(response.to_dict())
                        
                        messages.success(request, 'Configurações TokenAI atualizadas com sucesso!')
                        return redirect('accounts:token_config', token_id=token.id)
                    except Exception as e:
                        logger.exception(f"Erro ao salvar TokenAIConfiguration para token {token_id}: {e}")
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            response = APPResponse(
                                success=False,
                                error=f'Erro ao salvar as configurações: {str(e)}'
                            )
                            return JsonResponse(response.to_dict(), status=500)
                        messages.error(request, f'Erro ao salvar as configurações TokenAI: {str(e)}')
            else:
                logger.warning(f"Formulário TokenAI inválido para token {token_id}: {form.errors}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    errors = {field: str(error) for field, error in form.errors.items()}
                    response = APPResponse(
                        success=False,
                        error='Corrija os erros no formulário',
                        data={'errors': errors}
                    )
                    return JsonResponse(response.to_dict(), status=400)
                else:
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
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = APPResponse(
                success=False,
                error='Token não encontrado'
            )
            return JsonResponse(response.to_dict(), status=404)
        messages.error(request, 'Token não encontrado.')
        return redirect('accounts:tokens_manage')
    except Exception as e:
        logger.exception(f"Erro ao acessar configuração TokenAI para token {token_id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = APPResponse(
                success=False,
                error='Ocorreu um erro ao processar a requisição'
            )
            return JsonResponse(response.to_dict(), status=500)
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

@login_required
def token_ai_toggle(request: HttpRequest) -> JsonResponse:
    """Processa ativação/desativação em massa de IAs para múltiplos tokens.
    
    Recebe um payload JSON com a estrutura:
    {
        'token_id1': {
            'ai_id1': True,
            'ai_id2': False,
            ...
        },
        'token_id2': {
            'ai_id1': True,
            'ai_id2': False,
            ...
        }
    }
    
    Args:
        request: Requisição HTTP com payload JSON.
        
    Returns:
        JsonResponse: Resposta com status de sucesso ou erro.
    """
    user = request.user
    
    if request.method != 'POST':
        response = APPResponse(
            success=False,
            error='Método não permitido'
        )
        return JsonResponse(response.to_dict(), status=405)
    
    try:
        data = json.loads(request.body)
        
        if not isinstance(data, dict):
            raise ValueError("Formato de dados inválido. Esperado um objeto JSON.")
        
        results = {}
        errors = []
        
        with transaction.atomic():
            for token_id, ai_configs in data.items():
                try:
                    # Verificar se o token pertence ao usuário
                    token = get_object_or_404(UserToken, id=token_id, user=user)
                    
                    # Processar cada configuração de IA para este token
                    token_results = {}
                    for ai_id, enable in ai_configs.items():
                        try:
                            # Verificar se a configuração de IA pertence ao usuário
                            ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=user)
                            
                            # Atualizar ou criar a configuração
                            config, created = AIClientTokenConfig.objects.update_or_create(
                                token=token,
                                ai_config=ai_config,
                                defaults={'enabled': enable}
                            )
                            
                            action = "ativada" if enable else "desativada"
                            logger.info(f"IA {ai_id} {action} para token '{token.name}' (ID: {token_id})")
                            token_results[ai_id] = True
                            
                        except Exception as ai_error:
                            token_results[ai_id] = False
                            logger.error(f"Erro ao configurar IA {ai_id} para token {token_id}: {ai_error}")
                            errors.append(f"Erro ao configurar IA {ai_id} para token {token_id}: {str(ai_error)}")
                    
                    results[token_id] = token_results
                    
                except Exception as token_error:
                    results[token_id] = False
                    logger.error(f"Erro ao processar token {token_id}: {token_error}")
                    errors.append(f"Erro ao processar token {token_id}: {str(token_error)}")
        
        response_data = {
            'results': results
        }
        
        if errors:
            response = APPResponse(
                success=len(errors) == 0,
                data=response_data,
                error=errors[0] if errors else None,
                errors=errors
            )
            return JsonResponse(response.to_dict(), status=207)  # 207 Multi-Status
        
        response = APPResponse(
            success=True,
            data=response_data
        )
        return JsonResponse(response.to_dict())
        
    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON na requisição")
        response = APPResponse(
            success=False,
            error='Formato de dados inválido. JSON malformado.'
        )
        return JsonResponse(response.to_dict(), status=400)
        
    except Exception as e:
        logger.exception(f"Erro ao processar configuração em massa: {e}")
        response = APPResponse(
            success=False,
            error=f'Erro ao processar a requisição: {str(e)}'
        )
        return JsonResponse(response.to_dict(), status=500)
