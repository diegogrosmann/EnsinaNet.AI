import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse

from accounts.models import UserToken
from ai_config.models import TokenAIConfiguration
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
