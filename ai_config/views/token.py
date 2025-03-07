import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse

from accounts.models import UserToken
from ai_config.models import TokenAIConfiguration, AIClientConfiguration, AIClientTokenConfig
from ai_config.forms import TokenAIConfigurationForm

logger = logging.getLogger(__name__)

@login_required
def prompt_config(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia as configurações de prompt para o token.

    Args:
        request (HttpRequest): Requisição HTTP.
        token_id (str): Identificador do token.

    Returns:
        HttpResponse: Página com o formulário das configurações do token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    token_ai_config, _ = TokenAIConfiguration.objects.get_or_create(token=token)
    if request.method == 'POST':
        form = TokenAIConfigurationForm(request.POST, request.FILES, instance=token_ai_config, user=user)
        if form.is_valid():
            # Validação adicional do prompt
            prompt = form.cleaned_data.get('prompt', '').strip()
            if not prompt:
                form.add_error('prompt', 'Este campo é obrigatório.')
                messages.error(request, 'O campo Prompt é obrigatório.')
            else:
                try:
                    form.save()
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'success', 'message': 'Configurações salvas com sucesso!'})
                    messages.success(request, 'Configurações TokenAI atualizadas com sucesso!')
                    return redirect('accounts:token_config', token_id=token.id)
                except Exception as e:
                    logger.exception(f"Erro ao salvar TokenAIConfiguration: {e}")
                    messages.error(request, 'Erro ao salvar as configurações TokenAI. Tente novamente.')
        else:
            if 'prompt' in form.errors:
                messages.error(request, 'O campo Prompt é obrigatório.')
            else:
                messages.error(request, 'Corrija os erros no formulário TokenAI.')
    else:
        form = TokenAIConfigurationForm(instance=token_ai_config, user=user)
    context = {'token': token, 'form': form}
    return render(request, 'token/prompt_config.html', context)

@login_required
def token_ai_link(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia a vinculação e ativação de IAs ao token.

    Args:
        request (HttpRequest): Requisição HTTP.
        token_id (str): Identificador do token.

    Returns:
        HttpResponse: Página com lista de IAs disponíveis para o token.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    
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
        ai_config_ids = request.POST.getlist('ai_configs')
        enabled_ids = request.POST.getlist('enabled_configs')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            # Converter os IDs para inteiros
            ai_config_ids = [int(id) for id in ai_config_ids] if ai_config_ids else []
            enabled_ids = [int(id) for id in enabled_ids] if enabled_ids else []
            
            # Para requisições AJAX de um único toggle
            if is_ajax:
                # Identificar a IA que está sendo manipulada
                # Se estamos desativando uma IA, precisamos encontrá-la indiretamente
                toggled_ai_id = None
                
                # Verificar se temos uma IA no ai_configs (caso de ativação)
                if ai_config_ids:
                    toggled_ai_id = ai_config_ids[0]
                    # Atualizar ou criar a configuração
                    is_enabled = toggled_ai_id in enabled_ids
                    AIClientTokenConfig.objects.update_or_create(
                        token=token,
                        ai_config_id=toggled_ai_id,
                        defaults={'enabled': is_enabled}
                    )
                # Se não temos IA em ai_configs, estamos desativando
                else:
                    # Determinar qual IA está sendo desativada (usando parâmetros da requisição)
                    # Podemos identificar indiretamente pegando o ID da requisição direta
                    ai_id_param = request.POST.get('ai_id')
                    if ai_id_param:
                        toggled_ai_id = int(ai_id_param)
                        # Desativar a configuração
                        config = AIClientTokenConfig.objects.filter(
                            token=token, 
                            ai_config_id=toggled_ai_id
                        ).first()
                        
                        if config:
                            config.enabled = False
                            config.save()
            else:
                # Comportamento padrão para envios de formulário completo
                # Remover vinculações que não estão mais selecionadas
                AIClientTokenConfig.objects.filter(token=token).exclude(ai_config_id__in=ai_config_ids).delete()
                
                # Adicionar ou atualizar vinculações
                for ai_config_id in ai_config_ids:
                    is_enabled = ai_config_id in enabled_ids
                    AIClientTokenConfig.objects.update_or_create(
                        token=token,
                        ai_config_id=ai_config_id,
                        defaults={'enabled': is_enabled}
                    )
            
            if not is_ajax:
                messages.success(request, 'Configurações de IA atualizadas com sucesso!')
                return redirect('ai_config:token_ai_link', token_id=token.id)
            else:
                return JsonResponse({'status': 'success'})
        
        except Exception as e:
            logger.exception(f"Erro ao atualizar vinculações de IA: {e}")
            if not is_ajax:
                messages.error(request, 'Ocorreu um erro ao salvar as vinculações de IA.')
                return redirect('ai_config:token_ai_link', token_id=token.id)
            else:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    context = {
        'token': token,
        'ai_configs': user_ai_configs,
        'linked_config_ids': linked_config_ids,
        'enabled_config_ids': enabled_config_ids,
        'unique_clients': unique_clients  # Adicionar os clientes únicos ao contexto
    }
    
    return render(request, 'token/ai_link.html', context)
