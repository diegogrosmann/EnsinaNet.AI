"""
Views para configuração de tokens e prompts.

Este módulo contém funções para gerenciar configurações de prompt e vinculação de tokens
com clientes de IA, permitindo a personalização de instruções e prompts.

A documentação segue o padrão Google e os logs/exceções são tratados de forma padronizada.
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
from core.types import APPResponse, APPError

logger = logging.getLogger(__name__)


@login_required
def prompt_config(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia as configurações de prompt para o token.

    Permite definir instruções base, prompts e respostas personalizadas para um token específico.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        token_id (str): Identificador do token.

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
                            response = APPResponse.create_success(data={'message': 'Configurações salvas com sucesso!'})
                            return JsonResponse(response.to_dict())
                        messages.success(request, 'Configurações TokenAI atualizadas com sucesso!')
                        return redirect('accounts:token_config', token_id=token.id)
                    except Exception as e:
                        logger.exception(f"Erro ao salvar TokenAIConfiguration para token {token_id}: {e}")
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            error = APPError(message=f'Erro ao salvar as configurações: {str(e)}', status_code=500)
                            response = APPResponse.create_failure(error=error)
                            return JsonResponse(response.to_dict(), status=500)
                        messages.error(request, f'Erro ao salvar as configurações TokenAI: {str(e)}')
            else:
                logger.warning(f"Formulário TokenAI inválido para token {token_id}: {form.errors}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    errors = {field: str(error) for field, error in form.errors.items()}
                    response = APPResponse.create_failure(data={'errors': errors}, error=APPError(message='Corrija os erros no formulário', status_code=400))
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
            error = APPError(message='Token não encontrado', status_code=404)
            response = APPResponse.create_failure(error=error)
            return JsonResponse(response.to_dict(), status=404)
        messages.error(request, 'Token não encontrado.')
        return redirect('accounts:tokens_manage')
    except Exception as e:
        logger.exception(f"Erro ao acessar configuração TokenAI para token {token_id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error = APPError(message='Ocorreu um erro ao processar a requisição', status_code=500)
            response = APPResponse.create_failure(error=error)
            return JsonResponse(response.to_dict(), status=500)
        messages.error(request, 'Ocorreu um erro ao carregar a configuração. Tente novamente mais tarde.')
        return redirect('accounts:tokens_manage')


@login_required
def token_ai_link(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia a vinculação e ativação de IAs ao token.

    Permite vincular várias IAs a um token e ativá-las/desativá-las.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        token_id (str): Identificador do token.

    Returns:
        HttpResponse: Página com lista de IAs disponíveis para o token.
    """
    user = request.user
    try:
        token = get_object_or_404(UserToken, id=token_id, user=user)
        logger.debug(f"Acessando configurações de vínculo para token '{token.name}' (ID: {token_id})")
        user_ai_configs = AIClientConfiguration.objects.filter(user=user)
        linked_config_ids = {config.ai_config_id for config in AIClientTokenConfig.objects.filter(token=token)}
        enabled_config_ids = {config.ai_config_id for config in AIClientTokenConfig.objects.filter(token=token, enabled=True)}
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
            'token_config': {
                'token_id': 'uuid-do-token',
                'ai_configs': {'ai_id1': True, 'ai_id2': False, ...}
            }
        }

    Args:
        request (HttpRequest): Requisição HTTP com payload JSON.

    Returns:
        JsonResponse: Resposta com status de sucesso ou erro.
    """
    user = request.user
    if request.method != 'POST':
        error = APPError(message='Método não permitido', status_code=405)
        response = APPResponse.create_failure(error=error)
        return JsonResponse(response.to_dict(), status=405)
    try:
        # Detectar formato dos dados: JSON ou form data
        if request.content_type and 'application/json' in request.content_type and request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                logger.error("Erro ao decodificar JSON na requisição", exc_info=True)
                error = APPError(message='Formato de dados inválido. JSON malformado.', status_code=400)
                response = APPResponse.create_failure(error=error)
                return JsonResponse(response.to_dict(), status=400)
        else:
            # Se não é JSON, obter dados do formulário
            data = dict(request.POST.items())
            
        if not data:
            error = APPError(message='Nenhum dado recebido', status_code=400)
            response = APPResponse.create_failure(error=error)
            return JsonResponse(response.to_dict(), status=400)
        
        results = {}
        errors = []
        
        # NOVO: Processar o formato atualizado do payload
        with transaction.atomic():
            if 'token_config' in data:
                token_config = data['token_config']
                token_id = token_config.get('token_id')
                ai_configs = token_config.get('ai_configs', {})
                
                if not token_id or not ai_configs:
                    error = APPError(message='Dados incompletos', status_code=400)
                    response = APPResponse.create_failure(error=error)
                    return JsonResponse(response.to_dict(), status=400)
                
                try:
                    token = get_object_or_404(UserToken, id=token_id, user=user)
                    token_results = {}
                    
                    for ai_id, enable in ai_configs.items():
                        try:
                            ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=user)
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
                            logger.error(f"Erro ao configurar IA {ai_id} para token {token_id}: {ai_error}", exc_info=True)
                            errors.append(f"Erro ao configurar IA {ai_id} para token {token_id}: {str(ai_error)}")
                    
                    results[token_id] = token_results
                except Exception as token_error:
                    results[token_id] = False
                    logger.error(f"Erro ao processar token {token_id}: {token_error}", exc_info=True)
                    errors.append(f"Erro ao processar token {token_id}: {str(token_error)}")
            else:
                # Manter compatibilidade com o formato antigo
                for token_id, ai_configs in data.items():
                    # Converter string em dict se necessário (caso de form data)
                    if isinstance(ai_configs, str):
                        try:
                            ai_configs = json.loads(ai_configs)
                        except json.JSONDecodeError:
                            logger.error(f"Erro ao decodificar configs para token {token_id}", exc_info=True)
                            errors.append(f"Formato inválido para token {token_id}")
                            continue
                    
                    try:
                        token = get_object_or_404(UserToken, id=token_id, user=user)
                        token_results = {}
                        for ai_id, enable in ai_configs.items():
                            try:
                                ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=user)
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
                                logger.error(f"Erro ao configurar IA {ai_id} para token {token_id}: {ai_error}", exc_info=True)
                                errors.append(f"Erro ao configurar IA {ai_id} para token {token_id}: {str(ai_error)}")
                        results[token_id] = token_results
                    except Exception as token_error:
                        results[token_id] = False
                        logger.error(f"Erro ao processar token {token_id}: {token_error}", exc_info=True)
                        errors.append(f"Erro ao processar token {token_id}: {str(token_error)}")
        
        response_data = {'results': results}
        if errors:
            response = APPResponse.create_failure(error=APPError(message=errors[0], status_code=207))
            return JsonResponse(response.to_dict(), status=207)
        response = APPResponse.create_success(data=response_data)
        return JsonResponse(response.to_dict())
    except json.JSONDecodeError:
        logger.error("Erro ao decodificar JSON na requisição", exc_info=True)
        error = APPError(message='Formato de dados inválido. JSON malformado.', status_code=400)
        response = APPResponse.create_failure(error=error)
        return JsonResponse(response.to_dict(), status=400)
    except Exception as e:
        logger.exception(f"Erro ao processar configuração em massa: {e}")
        error = APPError(message=f'Erro ao processar a requisição: {str(e)}', status_code=500)
        response = APPResponse.create_failure(error=error)
        return JsonResponse(response.to_dict(), status=500)


@login_required
def get_ai_models(request: HttpRequest, ai_client_id: int) -> JsonResponse:
    """Lista modelos disponíveis para um cliente de IA específico.

    Retorna uma lista dos modelos base e dos modelos treinados pelo usuário atual.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        ai_client_id (int): ID da configuração global de cliente de IA.

    Returns:
        JsonResponse: Lista de modelos disponíveis.
    """
    try:
        from ai_config.models import AIClientGlobalConfiguration  # Import local para evitar dependência circular
        ai_client = get_object_or_404(AIClientGlobalConfiguration, id=ai_client_id)
        logger.debug(f"Listando modelos para cliente IA {ai_client.name}")
        client_instance = ai_client.create_api_client_instance()
        if not hasattr(client_instance, 'api_list_models'):
            logger.warning(f"Cliente {ai_client.api_client_class} não suporta listagem de modelos")
            error = APPError(message='Este cliente de IA não suporta listagem de modelos', status_code=400)
            response = APPResponse.create_failure(error)
            return JsonResponse(response.to_dict(), status=400)

        models = client_instance.api_list_models(list_trained_models=True, list_base_models=True)
        from ai_config.models import AITraining
        user_trained_models = set(AITraining.objects.filter(ai_config__user=request.user, status='completed').values_list('model_name', flat=True))
        base_models = []
        trained_models = []
        for model in models:
            model_data = {'id': model.id, 'name': model.name}
            if model.is_fine_tuned:
                if model.id in user_trained_models:
                    trained_models.append(model_data)
            else:
                base_models.append(model_data)
        response = APPResponse.create_success(data={'models': {'base': base_models, 'trained': trained_models}})
        return JsonResponse(response.to_dict())
    except Exception as e:
        logger.error(f"Erro ao listar modelos para cliente IA {ai_client_id}: {str(e)}", exc_info=True)
        error = APPError(message=f'Erro ao carregar modelos: {str(e)}', status_code=500)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)
