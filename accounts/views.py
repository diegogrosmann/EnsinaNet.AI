"""
Views para a aplicação accounts.

Este módulo contém funções e classes que gerenciam o registro, login, logout,
gerenciamento de tokens, configuração, redefinição de senha e confirmação de email.
"""

import logging
from typing import Any, Dict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout, get_user_model, login
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.safestring import mark_safe

from allauth.account.views import ConfirmEmailView
from allauth.account.utils import send_email_confirmation
from allauth.account.models import EmailAddress



from .forms import (
    CustomUserCreationForm,
    TokenForm,
    EmailAuthenticationForm,
    UserTokenForm,
    UserSettingsForm,
)
from .models import UserToken, Profile

from ai_config.models import AIClientGlobalConfiguration

logger = logging.getLogger(__name__)
User = get_user_model()

### Autenticação e Registro ###

def auth_register(request: HttpRequest) -> HttpResponse:
    """Registra um novo usuário e envia email de confirmação.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada ou redirecionamento para a página de login.
    """
    from django.db import transaction
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    send_email_confirmation(request, user)
                logger.info(f"Usuário registrado: {user.email}")
                messages.success(request, 'Conta criada com sucesso! Verifique seu email para confirmação.')
                return redirect('accounts:login')
            except Exception as e:
                logger.exception(f"Erro durante registro de usuário: {e}")
                messages.error(request, 'Erro ao criar a conta. Tente novamente.')
        else:
            logger.warning(f"Registro inválido: {form.errors}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/registration/register.html', {'form': form})


def auth_login(request: HttpRequest) -> HttpResponse:
    """Realiza autenticação e login do usuário.

    Se o usuário já estiver logado, redireciona para 'tokens_manage'.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada ou redirecionamento após login.
    """
    if request.user.is_authenticated:
        # Atualizar redirecionamento
        return redirect('accounts:tokens_manage')

    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():

            login(request, form.get_user())
            return redirect('accounts:tokens_manage')
        else:
            messages.error(request, form.errors.get('__all__','Email ou senha inválidos.'))    
            return redirect('accounts:login')
    else:
        form = EmailAuthenticationForm()
    return render(request, 'accounts/registration/login.html', {'form': form})


@login_required
def auth_logout(request: HttpRequest) -> HttpResponse:
    """Realiza o logout do usuário atual.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Redirecionamento para a página de login.
    """
    logger.info(f"Logout do usuário: {request.user.email}")
    logout(request)
    messages.success(request, 'Logout realizado com sucesso!')
    return redirect('accounts:login')

def auth_resend_confirmation(request: HttpRequest) -> HttpResponse:
    """Reenvia o email de confirmação para o usuário informado.
    
    Não requer autenticação, apenas email e senha válidos.
    """
    # Pré-preenche o email se fornecido via GET
    initial_email = request.GET.get('email', '')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                email_address = EmailAddress.objects.filter(user=user, email=email).first()
                if email_address and not email_address.verified:
                    send_email_confirmation(request, user)
                    messages.success(request, 'Email de confirmação reenviado com sucesso.')
                else:
                    messages.info(request, 'Este email já foi confirmado.')
            else:
                messages.error(request, 'Credenciais inválidas.')
                return redirect('accounts:resend_confirmation')
        except User.DoesNotExist:
            messages.error(request, 'Credenciais inválidas.')
            return redirect('accounts:resend_confirmation')
        
        return redirect('accounts:login')
        
    return render(request, 'accounts/registration/resend_confirmation.html', {
        'initial_email': initial_email
    })

### Redefinição de Senha ###

class CustomPasswordResetView(PasswordResetView):
    """
    View customizada para redefinição de senha no padrão.

    Attributes:
        template_name (str): Caminho do template para o formulário de reset de senha.
        email_template_name (str): Caminho do template utilizado no envio do email.
    """

    template_name = 'accounts/registration/password_reset_form.html'
    html_email_template_name = 'accounts/registration/password_reset_email.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Retorna o contexto atualizado com informações do site."""
        context = super().get_context_data(**kwargs)
        current_site = get_current_site(self.request)
        context.update({
            'domain': current_site.domain,
            'site_name': current_site.name,
            'protocol': 'https' if self.request.is_secure() else 'http',
        })
        return context

    def send_mail(self, *args: Any, **kwargs: Any) -> None:
        """Envia o email de redefinição de senha e registra o log da operação."""
        try:
            super().send_mail(*args, **kwargs)
            logger.info(f"E-mail de redefinição enviado para {kwargs.get('context', {}).get('email')}.")
        except Exception as e:
            logger.exception("Erro ao enviar email de redefinição:")
            messages.error(self.request, 'Erro ao enviar o email.')


def password_reset_done(request: HttpRequest) -> HttpResponse:
    """Exibe a página de confirmação após solicitar o reset de senha."""
    from django.contrib.auth.views import PasswordResetDoneView
    return PasswordResetDoneView.as_view(template_name='accounts/registration/password_reset_done.html')(request)


def password_reset_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Exibe a página para confirmação do reset de senha."""
    from django.contrib.auth.views import PasswordResetConfirmView
    return PasswordResetConfirmView.as_view(template_name='accounts/registration/password_reset_confirm.html')(
        request, uidb64=uidb64, token=token
    )


def password_reset_complete(request: HttpRequest) -> HttpResponse:
    """Exibe a página informando a conclusão do reset de senha."""
    from django.contrib.auth.views import PasswordResetCompleteView
    return PasswordResetCompleteView.as_view(template_name='accounts/registration/password_reset_complete.html')(request)


### Confirmação de Email ###

class CustomConfirmEmailView(ConfirmEmailView):
    """
    View customizada para confirmação de email no padrão Google.

    Esta view personaliza o processo de confirmação de email, ativando o usuário
    e enviando notificação para o administrador.
    """

    def get(self, request: HttpRequest, key: str, *args: Any, **kwargs: Any) -> HttpResponse:
        """Realiza a confirmação do email e ativa o usuário."""
        self.kwargs['key'] = key
        try:
            confirmation = self.get_object()
            confirmation.confirm(request)
            user = confirmation.email_address.user
            user.is_active = True
            user.save()
            logger.info(f"Email confirmado para {user.email}")
            admin_email = settings.ADMIN_EMAIL
            subject = 'Novo Usuário Confirmado'
            message = f'O usuário "{user.email}" confirmou seu email.'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [admin_email])
            messages.success(request, 'Email confirmado com sucesso!')
            return redirect('accounts:login')
        except Exception as e:
            logger.exception("Erro na confirmação de email:")
            messages.error(request, 'Erro na confirmação de email. Contate o suporte.')
            return redirect('accounts:register')

### Gerenciamento de Tokens ###

@login_required
def tokens_manage(request: HttpRequest) -> HttpResponse:
    """Gerencia tokens do usuário.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada com o contexto atualizado.
    """
    user = request.user
    tokens = UserToken.objects.filter(user=user)
    available_ais = [
        (obj.api_client_class, obj.api_client_class)
        for obj in AIClientGlobalConfiguration.objects.all()
    ]
    context: Dict[str, Any] = {
        'tokens': tokens,
        'is_approved': user.profile.is_approved,
        'available_ais': available_ais,
        'form': TokenForm(),
    }
    return render(request, 'accounts/manage/tokens_manage.html', context)


@login_required
def token_create(request: HttpRequest) -> HttpResponse:
    """Cria um novo token para o usuário.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Redirecionamento ou resposta HTTP apropriada.
    """
    if request.method != 'POST':
        return redirect('accounts:tokens_manage')

    user = request.user
    form = TokenForm(request.POST, user=user)
    
    if not form.is_valid():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'accounts/manage/modals/create_token_modal.html', {'form': form})
        messages.error(request, 'Formulário inválido.')
        return redirect('accounts:tokens_manage')

    if not user.profile.is_approved:
        messages.error(request, 'Sua conta não foi aprovada.')
        logger.warning(f"Tentativa de criação de token sem aprovação: {user.email}")
        return redirect('accounts:tokens_manage')

    try:
        token = form.save(commit=False)
        token.user = user
        token.save()
        logger.info(f"Token criado: {token.name} para {user.email}")
        messages.success(request, 'Token criado com sucesso!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponse()
        return redirect('accounts:token_config', token_id=token.id)
    except Exception as e:
        logger.exception(f"Erro ao criar token para {user.email}:")
        messages.error(request, 'Erro ao criar token.')
        return redirect('accounts:tokens_manage')


@login_required
def token_delete(request: HttpRequest, token_id: str) -> HttpResponse:
    token = get_object_or_404(UserToken, id=token_id, user=request.user)
    if request.method == 'POST':
        try:
            token.delete()
            logger.info(f"Token deletado: {token.name} por {request.user.email}")
            messages.success(request, 'Token deletado com sucesso!')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Token deletado com sucesso!'})
            
            return redirect('accounts:tokens_manage')
        except Exception as e:
            logger.exception(f"Erro ao deletar token {token.name}:")
            messages.error(request, 'Erro ao deletar token.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'accounts/manage/delete_token.html', {'token': token})


@login_required
def token_edit_name(request: HttpRequest, token_id: str) -> HttpResponse:
    """Atualiza o nome de um token.
    
    Args:
        request (HttpRequest): Requisição HTTP
        token_id (str): ID do token a ser editado
        
    Returns:
        HttpResponse: Redirecionamento após atualização
    """
    token = get_object_or_404(UserToken, id=token_id, user=request.user)
    if request.method == 'POST':
        new_name = request.POST.get('name')
        if new_name and new_name != token.name:
            try:
                token.name = new_name
                token.save()
                messages.success(request, 'Nome do token atualizado com sucesso!')
            except Exception as e:
                logger.error(f"Erro ao atualizar nome do token: {e}")
                messages.error(request, 'Erro ao atualizar nome do token.')
        return redirect('accounts:token_config', token_id=token_id)
    return redirect('accounts:token_config', token_id=token_id)


@login_required
def token_config(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia as configurações específicas de um token.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.
        token_id (str): Identificador do token a ser configurado.

    Returns:
        HttpResponse: Página renderizada com as configurações atualizadas.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    if request.method == 'POST':
        form = UserTokenForm(request.POST, request.FILES, instance=token)
        if form.is_valid():
            try:
                token = form.save()
                logger.info(f"Configurações atualizadas para token: {token.name}")
                messages.success(request, 'Configurações atualizadas com sucesso!')
                return redirect('accounts:token_config', token_id=token.id)
            except Exception as e:
                logger.exception("Erro ao atualizar configurações:")
                messages.error(request, 'Erro ao salvar configurações.')
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
            messages.error(request, 'Corrija os erros no formulário.')
    else:
        form = UserTokenForm(instance=token)
    available_ais = [
        (obj.api_client_class, obj.api_client_class)
        for obj in AIClientGlobalConfiguration.objects.all()
    ]
    context = {
        'token': token,
        'form': form,
        'available_ais': available_ais,
    }
    return render(request, 'accounts/manage/token.config.html', context)

### Configurações do Usuário ###

@login_required
def user_settings(request: HttpRequest) -> HttpResponse:
    """Gerencia as configurações do usuário.

    Args:
        request (HttpRequest): Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada com o formulário de configurações do usuário.
    """
    user = request.user
    # Garante que existe um profile
    Profile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configurações atualizadas com sucesso!')
            return redirect('accounts:user_settings')
        else:
            messages.error(request, 'Erro ao atualizar configurações. Verifique os dados informados.')
    else:
        form = UserSettingsForm(instance=user)
    
    context = {
        'form': form,
    }
    return render(request, 'accounts/user_settings.html', context)