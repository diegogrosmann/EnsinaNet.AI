import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.db.models import Count
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.db import DatabaseError
import json

from accounts.models import UserToken

from ..models import AIClientConfiguration, AIClientTokenConfig
from ..forms import AIClientConfigurationForm

logger = logging.getLogger(__name__)

@login_required
def manage_ai(request):
    """Lista todas as IAs configuradas."""
    try:
        search_query = request.GET.get('search', '')
        api_type = request.GET.get('api_type', '')
        
        # Query base
        queryset = AIClientConfiguration.objects.annotate(
            token_count=Count('tokens')  # Corrigido
        ).order_by('name')  # Adiciona ordenação por nome
        
        # Aplica filtros
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        
        if api_type:
            queryset = queryset.filter(ai_client__api_client_class=api_type)
        
        # Obtém lista única de tipos de API
        api_types = AIClientConfiguration.objects.values_list(
            'ai_client__api_client_class', flat=True
        ).distinct().order_by('ai_client__api_client_class')
        
        # Paginação
        paginator = Paginator(queryset, 10)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'ai_clients': page_obj,
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
                'has_next': page_obj.has_next(),
                'has_prev': page_obj.has_previous(),
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'total': paginator.count,
            })

        return render(request, 'ai_client/manage.html', context)

    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao listar IAs: {str(e)}")
        messages.error(request, "Erro ao carregar a lista de IAs. Tente novamente mais tarde.")
        return render(request, 'ai_client/manage.html', {'error': True})

@login_required
def create_ai(request):
    """Cria uma nova configuração global de IA."""
    try:
        if request.method == 'POST':
            form = AIClientConfigurationForm(request.POST)
            if form.is_valid():
                ai_config = form.save(commit=False)
                ai_config.user = request.user
                ai_config.save()
                messages.success(request, 'IA criada com sucesso!')
                
                # Obter URL de retorno do formulário ou usar fallback
                next_url = request.POST.get('next')
                if next_url and next_url.startswith('/'):  # Verificar se é uma URL interna válida
                    return redirect(next_url)
                return redirect('ai_config:ai_manage')  # Fallback
            else:
                messages.error(request, 'Corrija os erros no formulário.')
        else:
            form = AIClientConfigurationForm()
        
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

@login_required
def edit_ai(request, ai_id):
    """Edita uma configuração global de IA existente."""
    try:
        ai = get_object_or_404(AIClientConfiguration, id=ai_id)
        
        if request.method == 'POST':
            form = AIClientConfigurationForm(request.POST, instance=ai)
            if form.is_valid():
                form.save()
                messages.success(request, 'IA atualizada com sucesso!')
                
                # Obter URL de retorno do formulário ou usar fallback
                next_url = request.POST.get('next')
                if next_url and next_url.startswith('/'):  # Verificar se é uma URL interna válida
                    return redirect(next_url)
                return redirect('ai_config:ai_manage')  # Fallback
            else:
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
        messages.error(request, "IA não encontrada.")
        return redirect('ai_config:ai_manage')
    except DatabaseError as e:
        logger.error(f"Erro de banco de dados ao editar IA {ai_id}: {str(e)}")
        messages.error(request, "Erro ao atualizar IA. Tente novamente mais tarde.")
        return redirect('ai_config:ai_manage')

@login_required
def delete_ai(request, ai_id):
    """Remove uma configuração global de IA."""
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Método não permitido'
        }, status=405)
        
    try:
        ai = get_object_or_404(AIClientConfiguration, id=ai_id)
        name = ai.name
        ai.delete()
        
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
        logger.error(f"Erro inesperado ao excluir IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Erro inesperado ao excluir IA'
        }, status=500)

@login_required
def ai_available_tokens(request, ai_id):
    """Lista tokens disponíveis para uma IA específica e seu estado (vinculado ou não)."""
    try:
        # Verificar se a IA pertence ao usuário atual
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_id, user=request.user)
        
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
        
        return JsonResponse({
            'status': 'success',
            'tokens': tokens_data
        })
    except Exception as e:
        logger.exception(f"Erro ao listar tokens disponíveis para IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Ocorreu um erro ao carregar os tokens disponíveis.'
        }, status=500)

@login_required
def ai_link_token(request, ai_id, token_id):
    """Vincula ou desvincula um token específico a uma IA."""
    if request.method != 'POST':
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
        
        # Atualizar ou criar a configuração
        obj, created = AIClientTokenConfig.objects.update_or_create(
            token=token,
            ai_config=ai_config,
            defaults={'enabled': is_enabled}
        )
        
        # Se is_enabled for False e já existia a vinculação, remover a configuração
        if not is_enabled and not created:
            obj.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Token {"ativado" if is_enabled else "desativado"} com sucesso!'
        })
    
    except Exception as e:
        logger.exception(f"Erro ao vincular token {token_id} à IA {ai_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Ocorreu um erro ao processar sua solicitação.'
        }, status=500)