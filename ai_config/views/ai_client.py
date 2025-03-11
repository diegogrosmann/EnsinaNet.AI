"""
Views para gerenciamento de configurações de clientes de IA.

Este módulo contém funções para criar, editar, excluir e gerenciar
configurações de clientes de IA para diferentes usuários.
"""

import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db.models import Count
from django.template.loader import render_to_string
from django.db import DatabaseError, transaction

from accounts.models import UserToken

from ..models import AIClientConfiguration, AIClientTokenConfig
from ..forms import AIClientConfigurationForm

logger = logging.getLogger(__name__)

@login_required
def manage_ai(request: HttpRequest) -> HttpResponse:
    """Lista todas as IAs configuradas do usuário atual.
    
    Permite filtrar e paginar a lista de configurações de IA.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        HttpResponse: Página renderizada com a lista de IAs do usuário.
    """
    try:
        search_query = request.GET.get('search', '')
        api_type = request.GET.get('api_type', '')
        
        logger.debug(f"Listando IAs para usuário {request.user.email} com filtros: search={search_query}, api_type={api_type}")
        
        # Query base - filtrando apenas por IAs do usuário atual
        queryset = AIClientConfiguration.objects.filter(user=request.user).annotate(
            token_count=Count('tokens')
        ).order_by('name')
        
        # Aplica filtros
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
            logger.debug(f"Aplicando filtro de busca: '{search_query}'")
        
        if api_type:
            queryset = queryset.filter(ai_client__api_client_class=api_type)
            logger.debug(f"Aplicando filtro de tipo de API: '{api_type}'")
        
        # Obtém lista única de tipos de API
        api_types = AIClientConfiguration.objects.filter(user=request.user).values_list(
            'ai_client__api_client_class', flat=True
        ).distinct().order_by('ai_client__api_client_class')
        
        logger.debug(f"Total de IAs encontradas: {queryset.count()}")
        
        # MODIFICAÇÃO: Não usamos paginação no backend, já que fazemos isso no frontend
        # Enviamos todas as IAs para o JavaScript
        context = {
            'ai_clients': queryset,
            'api_types': api_types,
            'search_query': search_query,
            'selected_api': api_type,
        }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(
                'ai_client/partials/ai_table.html',
                context,
                request=request
            )
            return JsonResponse({
                'html': html,
                'total': queryset.count(),
            })

        return render(request, 'ai_client/manage.html', context)

    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao listar IAs: {str(e)}")
        messages.error(request, "Erro ao carregar a lista de IAs. Tente novamente mais tarde.")
        return render(request, 'ai_client/manage.html', {'error': True})
    except Exception as e:
        logger.exception(f"Erro inesperado ao listar IAs: {str(e)}")
        messages.error(request, "Ocorreu um erro inesperado. Por favor, tente novamente.")
        return render(request, 'ai_client/manage.html', {'error': True})

@login_required
def create_ai(request: HttpRequest) -> HttpResponse:
    """Cria uma nova configuração de IA.
    
    Exibe o formulário para criar uma nova configuração ou processa
    os dados de formulário recebidos.
    
    Args:
        request: Objeto de requisição HTTP.
        
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
                    
                    # Obter URL de retorno do formulário ou usar fallback
                    next_url = request.POST.get('next')
                    if next_url and next_url.startswith('/'):  # Verificar se é uma URL interna válida
                        return redirect(next_url)
                    return redirect('ai_config:ai_manage')  # Fallback
                except Exception as e:
                    logger.error(f"Erro ao salvar nova configuração de IA: {str(e)}")
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
        logger.error(f"Erro de banco de dados ao criar IA: {str(e)}")
        messages.error(request, "Erro ao criar IA. Tente novamente mais tarde.")
        return redirect('ai_config:ai_manage')
    except Exception as e:
        logger.exception(f"Erro inesperado ao criar IA: {str(e)}")
        messages.error(request, "Ocorreu um erro inesperado. Por favor, tente novamente.")
        return redirect('ai_config:ai_manage')

@login_required
def edit_ai(request: HttpRequest, ai_id: int) -> HttpResponse:
    """Edita uma configuração de IA existente.
    
    Exibe o formulário pré-preenchido para edição ou processa 
    os dados do formulário recebidos.
    
    Args:
        request: Objeto de requisição HTTP.
        ai_id: ID da configuração de IA a ser editada.
        
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
                    
                    # Obter URL de retorno do formulário ou usar fallback
                    next_url = request.POST.get('next')
                    if next_url and next_url.startswith('/'):  # Verificar se é uma URL interna válida
                        return redirect(next_url)
                    return redirect('ai_config:ai_manage')  # Fallback
                except Exception as e:
                    logger.error(f"Erro ao salvar alterações na IA {ai_id}: {str(e)}")
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
        logger.error(f"Erro de banco de dados ao editar IA {ai_id}: {str(e)}")
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
        request: Objeto de requisição HTTP.
        ai_id: ID da configuração de IA a ser removida.
        
    Returns:
        JsonResponse: Resposta JSON com status da operação.
    """
    if request.method != 'POST':
        logger.warning(f"Tentativa de exclusão de IA {ai_id} com método não permitido: {request.method}")
        return JsonResponse({
            'status': 'error',
            'message': 'Método não permitido'
        }, status=405)
        
    try:
        ai = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        name = ai.name
        logger.info(f"Excluindo IA '{name}' (ID: {ai_id}) para usuário {request.user.email}")
        
        with transaction.atomic():
            ai.delete()
        
        logger.info(f"IA '{name}' (ID: {ai_id}) excluída com sucesso")
        messages.success(request, f'IA "{name}" excluída com sucesso!')
        return JsonResponse({'status': 'success'})
    
    except AIClientConfiguration.DoesNotExist:
        logger.error(f"IA {ai_id} não encontrada para exclusão")
        return JsonResponse({
            'status': 'error',
            'message': 'IA não encontrada'
        }, status=404)
    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao excluir IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Erro ao excluir IA. Tente novamente mais tarde.'
        }, status=500)
    except Exception as e:
        logger.exception(f"Erro inesperado ao excluir IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Erro inesperado ao excluir IA'
        }, status=500)

@login_required
def ai_available_tokens(request: HttpRequest, ai_id: int) -> JsonResponse:
    """Lista tokens disponíveis para uma IA específica e seu estado (vinculado ou não).
    
    Args:
        request: Objeto de requisição HTTP.
        ai_id: ID da configuração de IA.
        
    Returns:
        JsonResponse: Lista de tokens com seu estado de vinculação.
    """
    try:
        # Verificar se a IA pertence ao usuário atual
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        logger.debug(f"Listando tokens disponíveis para IA '{ai_config.name}' (ID: {ai_id})")
        
        # Obter todos os tokens do usuário
        user_tokens = UserToken.objects.filter(user=request.user)
        
        # Obter configurações já vinculadas a esta IA
        token_configs = {
            config.token_id: config.enabled 
            for config in AIClientTokenConfig.objects.filter(ai_config=ai_config)
        }
        
        # Preparar dados para a resposta
        tokens_data = []
        for token in user_tokens:
            tokens_data.append({
                'id': str(token.id),
                'name': token.name,
                'linked': token.id in token_configs,
                'enabled': token_configs.get(token.id, False)
            })
        
        logger.debug(f"Encontrados {len(tokens_data)} tokens para IA {ai_id}")
        return JsonResponse({
            'status': 'success',
            'tokens': tokens_data
        })
    except AIClientConfiguration.DoesNotExist:
        logger.warning(f"Tentativa de listar tokens para IA inexistente (ID: {ai_id})")
        return JsonResponse({
            'status': 'error',
            'message': 'Configuração de IA não encontrada'
        }, status=404)
    except Exception as e:
        logger.exception(f"Erro ao listar tokens disponíveis para IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Ocorreu um erro ao carregar os tokens disponíveis.'
        }, status=500)

@login_required
def ai_link_token(request: HttpRequest, ai_id: int, token_id: str) -> JsonResponse:
    """Vincula ou desvincula um token específico a uma IA.
    
    Args:
        request: Objeto de requisição HTTP.
        ai_id: ID da configuração de IA.
        token_id: ID do token a ser vinculado/desvinculado.
        
    Returns:
        JsonResponse: Resposta JSON com status da operação.
    """
    if request.method != 'POST':
        logger.warning(f"Tentativa de vincular token {token_id} à IA {ai_id} com método não permitido: {request.method}")
        return JsonResponse({
            'status': 'error',
            'message': 'Método não permitido'
        }, status=405)
    
    try:
        # Verificar se a IA pertence ao usuário atual
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        
        # Verificar se o token pertence ao usuário atual
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        
        # Obter dados da requisição
        data = json.loads(request.body)
        is_enabled = data.get('enabled', False)
        
        logger.debug(f"Alterando vínculo entre token '{token.name}' e IA '{ai_config.name}': enabled={is_enabled}")
        
        # Atualizar ou criar a configuração em uma transação
        with transaction.atomic():
            obj, created = AIClientTokenConfig.objects.update_or_create(
                token=token,
                ai_config=ai_config,
                defaults={'enabled': is_enabled}
            )
            
            # Se is_enabled for False e já existia a vinculação, remover a configuração
            if not is_enabled and not created:
                obj.delete()
                logger.info(f"Token '{token.name}' desativado para IA '{ai_config.name}'")
            else:
                logger.info(f"Token '{token.name}' {'vinculado' if created else 'atualizado'} para IA '{ai_config.name}': enabled={is_enabled}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Token {"ativado" if is_enabled else "desativado"} com sucesso!'
        })
    
    except json.JSONDecodeError:
        logger.error(f"Erro ao decodificar JSON na solicitação de vínculo token {token_id} - IA {ai_id}")
        return JsonResponse({
            'status': 'error',
            'message': 'Formato de dados inválido.'
        }, status=400)
    except (AIClientConfiguration.DoesNotExist, UserToken.DoesNotExist):
        logger.warning(f"Tentativa de vincular token {token_id} a IA {ai_id} inexistente ou não pertencente ao usuário")
        return JsonResponse({
            'status': 'error',
            'message': 'Token ou IA não encontrados.'
        }, status=404)
    except Exception as e:
        logger.exception(f"Erro ao vincular token {token_id} à IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Ocorreu um erro ao processar sua solicitação.'
        }, status=500)