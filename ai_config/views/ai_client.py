"""
Views para gerenciamento de configurações de clientes de IA.

Este módulo contém funções para criar, editar, excluir e gerenciar configurações de clientes de IA
para diferentes usuários.

A documentação segue o padrão Google e os logs/exceções são tratados de forma padronizada.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db.models import Count
from django.template.loader import render_to_string
from django.db import DatabaseError, transaction

from accounts.models import UserToken
from ai_config.models import AIClientConfiguration, AIClientTokenConfig
from ai_config.forms import AIClientConfigurationForm
from core.types import APPResponse, APPError

logger = logging.getLogger(__name__)


@login_required
def manage_ai(request: HttpRequest) -> HttpResponse:
    """Lista todas as IAs configuradas do usuário atual.

    Permite filtrar e paginar a lista de configurações de IA.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada com a lista de IAs do usuário.
    """
    try:
        search_query = request.GET.get('search', '')
        api_type = request.GET.get('api_type', '')
        logger.debug(f"Listando IAs para usuário {request.user.email} com filtros: search={search_query}, api_type={api_type}")

        queryset = AIClientConfiguration.objects.filter(user=request.user).annotate(token_count=Count('tokens')).order_by('name')

        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
            logger.debug(f"Aplicando filtro de busca: '{search_query}'")
        if api_type:
            queryset = queryset.filter(ai_client__api_client_class=api_type)
            logger.debug(f"Aplicando filtro de tipo de API: '{api_type}'")

        api_types = AIClientConfiguration.objects.filter(user=request.user).values_list('ai_client__api_client_class', flat=True).distinct().order_by('ai_client__api_client_class')
        logger.debug(f"Total de IAs encontradas: {queryset.count()}")

        context = {
            'ai_clients': queryset,
            'api_types': api_types,
            'search_query': search_query,
            'selected_api': api_type,
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html_content = render_to_string('ai_client/partials/ai_table.html', context, request=request)
            response = APPResponse.create_success(data={'html': html_content, 'total': queryset.count()})
            return JsonResponse(response.to_dict())

        return render(request, 'ai_client/manage.html', context)

    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao listar IAs: {str(e)}", exc_info=True)
        messages.error(request, "Erro ao carregar a lista de IAs. Tente novamente mais tarde.")
        return render(request, 'ai_client/manage.html', {'error': True})
    except Exception as e:
        logger.exception(f"Erro inesperado ao listar IAs: {str(e)}")
        messages.error(request, "Ocorreu um erro inesperado. Por favor, tente novamente.")
        return render(request, 'ai_client/manage.html', {'error': True})


@login_required
def create_ai(request: HttpRequest) -> HttpResponse:
    """Cria uma nova configuração de IA.

    Exibe o formulário para criar uma nova configuração ou processa os dados recebidos.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página do formulário ou redirecionamento após criação.
    """
    try:
        if request.method == 'POST':
            form = AIClientConfigurationForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        ai_config = form.save(commit=False)
                        ai_config.user = request.user
                        ai_config.save()
                    logger.info(f"Nova IA '{ai_config.name}' criada por {request.user.email} (ID: {ai_config.id})")
                    messages.success(request, 'IA criada com sucesso!')
                    next_url = request.POST.get('next')
                    if next_url and next_url.startswith('/'):
                        return redirect(next_url)
                    return redirect('ai_config:ai_manage')
                except Exception as e:
                    logger.error(f"Erro ao salvar nova configuração de IA: {str(e)}", exc_info=True)
                    messages.error(request, f"Erro ao criar IA: {str(e)}")
            else:
                logger.warning(f"Formulário de criação de IA inválido: {form.errors}")
                messages.error(request, 'Corrija os erros no formulário.')
        else:
            form = AIClientConfigurationForm()
            logger.debug(f"Exibindo formulário de criação de IA para {request.user.email}")
        return render(request, 'ai_client/form.html', {
            'form': form,
            'title': 'Nova IA',
            'submit_text': 'Criar',
            'is_edit': False
        })
    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao criar IA: {str(e)}", exc_info=True)
        messages.error(request, "Erro ao criar IA. Tente novamente mais tarde.")
        return redirect('ai_config:ai_manage')
    except Exception as e:
        logger.exception(f"Erro inesperado ao criar IA: {str(e)}")
        messages.error(request, "Ocorreu um erro inesperado. Por favor, tente novamente.")
        return redirect('ai_config:ai_manage')


@login_required
def edit_ai(request: HttpRequest, ai_id: int) -> HttpResponse:
    """Edita uma configuração de IA existente.

    Exibe o formulário pré-preenchido para edição ou processa os dados do formulário recebidos.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        ai_id (int): ID da configuração de IA a ser editada.

    Returns:
        HttpResponse: Página do formulário ou redirecionamento após edição.
    """
    try:
        ai = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        logger.debug(f"Editando IA '{ai.name}' (ID: {ai_id}) para usuário {request.user.email}")
        if request.method == 'POST':
            form = AIClientConfigurationForm(request.POST, instance=ai)
            if form.is_valid():
                try:
                    form.save()
                    logger.info(f"IA '{ai.name}' (ID: {ai_id}) atualizada com sucesso por {request.user.email}")
                    messages.success(request, 'IA atualizada com sucesso!')
                    next_url = request.POST.get('next')
                    if next_url and next_url.startswith('/'):
                        return redirect(next_url)
                    return redirect('ai_config:ai_manage')
                except Exception as e:
                    logger.error(f"Erro ao salvar alterações na IA {ai_id}: {str(e)}", exc_info=True)
                    messages.error(request, f"Erro ao atualizar IA: {str(e)}")
            else:
                logger.warning(f"Formulário de edição inválido para IA {ai_id}: {form.errors}")
                messages.error(request, 'Corrija os erros no formulário.')
        else:
            form = AIClientConfigurationForm(instance=ai)
        return render(request, 'ai_client/form.html', {
            'form': form,
            'title': f'Editar IA: {ai.name}',
            'submit_text': 'Atualizar',
            'is_edit': True,
            'ai_config': ai
        })
    except AIClientConfiguration.DoesNotExist:
        logger.warning(f"Tentativa de edição de IA inexistente (ID: {ai_id}) por {request.user.email}")
        messages.error(request, "IA não encontrada.")
        return redirect('ai_config:ai_manage')
    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao editar IA {ai_id}: {str(e)}", exc_info=True)
        messages.error(request, "Erro ao atualizar IA. Tente novamente mais tarde.")
        return redirect('ai_config:ai_manage')
    except Exception as e:
        logger.exception(f"Erro inesperado ao editar IA {ai_id}: {str(e)}")
        messages.error(request, "Ocorreu um erro inesperado. Por favor, tente novamente.")
        return redirect('ai_config:ai_manage')


@login_required
def delete_ai(request: HttpRequest, ai_id: int) -> JsonResponse:
    """Remove uma configuração de IA.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        ai_id (int): ID da configuração de IA a ser removida.

    Returns:
        JsonResponse: Resposta JSON com status da operação.
    """
    if request.method != 'POST':
        logger.warning(f"Tentativa de exclusão de IA {ai_id} com método não permitido: {request.method}")
        error = APPError(message='Método não permitido', status_code=405)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=405)
    try:
        ai = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        name = ai.name
        logger.info(f"Excluindo IA '{name}' (ID: {ai_id}) para usuário {request.user.email}")
        with transaction.atomic():
            ai.delete()
        logger.info(f"IA '{name}' (ID: {ai_id}) excluída com sucesso")
        response = APPResponse.create_success(data={'message': 'IA excluída com sucesso'})
        return JsonResponse(response.to_dict())
    except AIClientConfiguration.DoesNotExist:
        logger.error(f"IA {ai_id} não encontrada para exclusão")
        error = APPError(message='IA não encontrada', status_code=404)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=404)
    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao excluir IA {ai_id}: {str(e)}", exc_info=True)
        error = APPError(message='Erro ao excluir IA. Tente novamente mais tarde.', status_code=500)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)
    except Exception as e:
        logger.exception(f"Erro inesperado ao excluir IA {ai_id}: {str(e)}")
        error = APPError(message='Erro inesperado ao excluir IA', status_code=500)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=500)


@login_required
def ai_available_tokens(request: HttpRequest, ai_id: int) -> JsonResponse:
    """Lista tokens disponíveis para uma IA específica e seu estado (vinculado ou não).

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        ai_id (int): ID da configuração de IA.

    Returns:
        JsonResponse: Lista de tokens com seu estado de vinculação.
    """
    try:
        ai_config =  get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        logger.debug(f"Listando tokens disponíveis para IA '{ai_config.name}' (ID: {ai_id})")
        user_tokens = UserToken.objects.filter(user=request.user)
        token_configs = {config.token_id: config.enabled for config in AIClientTokenConfig.objects.filter(ai_config=ai_config)}
        tokens_data = []
        for token in user_tokens:
            tokens_data.append({
                'id': str(token.id),
                'name': token.name,
                'linked': token.id in token_configs,
                'enabled': token_configs.get(token.id, False)
            })
        logger.debug(f"Encontrados {len(tokens_data)} tokens para IA {ai_id}")
        response = APPResponse.create_success(data={'tokens': tokens_data})
        return JsonResponse(response.to_dict())
    except AIClientConfiguration.DoesNotExist:
        logger.warning(f"Tentativa de listar tokens para IA inexistente (ID: {ai_id})")
        error = APPError(message='Configuração de IA não encontrada', status_code=404)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        logger.exception(f"Erro ao listar tokens disponíveis para IA {ai_id}: {str(e)}")
        error = APPError(message='Ocorreu um erro ao carregar os tokens disponíveis.', status_code=500)
        response = APPResponse.create_failure(error)
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
        from ai_config.models import AIClientGlobalConfiguration
        ai_client = get_object_or_404(AIClientGlobalConfiguration, id=ai_client_id)
        logger.debug(f"Listando modelos para cliente IA {ai_client.name}")
        client_instance = ai_client.create_api_client_instance()
        if not hasattr(client_instance, 'api_list_models'):
            logger.warning(f"Cliente {ai_client.api_client_class} não suporta listagem de modelos")
            error = APPError(message='Este cliente de IA não suporta listagem de modelos')
            response = APPResponse.create_failure(error)
            return JsonResponse(response.to_dict(), status=400)

        models = client_instance.api_list_models(list_trained_models=True, list_base_models=True)
        from ai_config.models import AITraining
        user_trained_models = set(AITraining.objects.filter(ai_config__user=request.user, status='completed')
                                   .values_list('model_name', flat=True))
        base_models = []
        trained_models = []
        for model in models:
            # Converte o id para string e utiliza o nome para comparação
            model_data = {'id': str(model.id), 'name': model.name}
            if model.is_fine_tuned:
                if model.name in user_trained_models:
                    trained_models.append(model_data)
            else:
                base_models.append(model_data)
        response = APPResponse.create_success(data={'models': {'base': base_models, 'trained': trained_models}})
        return JsonResponse(response.to_dict())
    except AIClientGlobalConfiguration.DoesNotExist:
        logger.warning(f"Cliente IA não encontrado: ID {ai_client_id}")
        error = APPError(message='Cliente IA não encontrado', status_code=404)
        response = APPResponse.create_failure(error)
        return JsonResponse(response.to_dict(), status=404)
    except Exception as e:
        logger.error(f"Erro ao listar modelos para cliente IA {ai_client_id}: {str(e)}", exc_info=True)
        # Garante que a resposta tenha a estrutura esperada, mesmo em caso de erro
        response = APPResponse.create_success(data={'models': {'base': [], 'trained': []}})
        return JsonResponse(response.to_dict())
