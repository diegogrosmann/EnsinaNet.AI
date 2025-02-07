import logging
from typing import Any, Dict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from allauth.account.views import ConfirmEmailView
from allauth.account.utils import send_email_confirmation

from .forms import (
    CustomUserCreationForm,
    TokenForm,
    EmailAuthenticationForm,
    UserTokenForm,
)
from .models import UserToken, Profile

from ai_config.forms import UserAITrainingFileForm  
from ai_config.models import AITrainingFile, AIClientGlobalConfiguration

logger = logging.getLogger(__name__)


def register_view(request: HttpRequest) -> HttpResponse:
    """
    Registra um novo usuário e envia email de confirmação.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                send_email_confirmation(request, user)
                logger.info(f"Usuário registrado: {user.email}")
                messages.success(request, 'Conta criada com sucesso! Verifique seu email para confirmação.')
                return redirect('login')
            except Exception as e:
                logger.exception("Erro durante registro de usuário:")
                messages.error(request, 'Erro ao criar a conta. Tente novamente.')
        else:
            logger.warning(f"Registro inválido: {form.errors}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/registration/register.html', {'form': form})


def login_view(request: HttpRequest) -> HttpResponse:
    """
    Efetua o login do usuário.
    """
    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(f"Usuário logado: {user.email}")
            messages.success(request, f'Bem-vindo, {user.email}!')
            return redirect('manage_tokens')
        else:
            logger.warning(f"Falha no login: {form.errors}")
    else:
        form = EmailAuthenticationForm()
    return render(request, 'accounts/registration/login.html', {'form': form})


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Realiza o logout do usuário.
    """
    logger.info(f"Logout do usuário: {request.user.email}")
    logout(request)
    messages.success(request, 'Logout realizado com sucesso!')
    return redirect('login')


@login_required
def manage_tokens(request: HttpRequest) -> HttpResponse:
    """
    Gerencia os tokens do usuário, permitindo criar tokens e fazer upload de arquivos de treinamento.
    """
    user = request.user
    tokens = UserToken.objects.filter(user=user)
    training_files = AITrainingFile.objects.filter(user=user)
    available_ais = [
        (obj.api_client_class, obj.api_client_class)
        for obj in AIClientGlobalConfiguration.objects.all()
    ]
    context: Dict[str, Any] = {
        'tokens': tokens,
        'training_files': training_files,
        'is_approved': user.profile.is_approved,
        'available_ais': available_ais,
        'form': TokenForm(),
        'training_file_form': UserAITrainingFileForm(),
    }

    if request.method == 'POST':
        if 'create_token' in request.POST:
            form = TokenForm(request.POST, user=user)
            if form.is_valid():
                if not user.profile.is_approved:
                    messages.error(request, 'Sua conta não foi aprovada.')
                    logger.warning(f"Tentativa de criação de token sem aprovação: {user.email}")
                    return redirect('manage_tokens')
                try:
                    token = form.save(commit=False)
                    token.user = user
                    token.save()
                    logger.info(f"Token criado: {token.name} para {user.email}")
                    messages.success(request, 'Token criado com sucesso!')
                    return redirect('manage_configurations', token_id=token.id)
                except Exception as e:
                    logger.exception(f"Erro ao criar token para {user.email}:")
                    messages.error(request, 'Erro ao criar token.')
            else:
                context['form'] = form
        elif 'upload_training_file' in request.POST:
            training_file_form = UserAITrainingFileForm(request.POST, request.FILES)
            if training_file_form.is_valid():
                try:
                    training_file = training_file_form.save(commit=False)
                    training_file.user = user
                    training_file.save()
                    logger.info(f"Arquivo de treinamento carregado por {user.email}")
                    messages.success(request, 'Arquivo de treinamento carregado com sucesso!')
                    return redirect('manage_tokens')
                except Exception as e:
                    logger.exception("Erro ao carregar arquivo de treinamento:")
                    messages.error(request, 'Erro ao carregar arquivo.')
            context['training_file_form'] = training_file_form
    return render(request, 'accounts/manage/manage_tokens.html', context)


@login_required
def delete_token(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Exclui um token específico.
    """
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    if request.method == 'POST':
        try:
            token.delete()
            logger.info(f"Token deletado: {token.name} por {user.email}")
            messages.success(request, 'Token deletado com sucesso!')
            return redirect('manage_tokens')
        except Exception as e:
            logger.exception(f"Erro ao deletar token {token.name}:")
            messages.error(request, 'Erro ao deletar token.')
    return render(request, 'accounts/manage/delete_token.html', {'token': token})


@login_required
def manage_configurations(request: HttpRequest, token_id: str) -> HttpResponse:
    """
    Gerencia as configurações específicas de um token.
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
                return redirect('manage_configurations', token_id=token.id)
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
    return render(request, 'accounts/manage/manage_configurations.html', context)


class CustomPasswordResetView(ConfirmEmailView):
    """
    View customizada para redefinição de senha.
    (Aqui, você pode integrar ou derivar da view padrão do Django.)
    """
    template_name = 'accounts/registration/password_reset_form.html'
    email_template_name = 'accounts/registration/password_reset_email.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        current_site = get_current_site(self.request)
        context.update({
            'domain': current_site.domain,
            'site_name': current_site.name,
            'protocol': 'https' if self.request.is_secure() else 'http',
        })
        return context

    def send_mail(self, *args: Any, **kwargs: Any) -> None:
        try:
            super().send_mail(*args, **kwargs)
            logger.info(f"E-mail de redefinição enviado para {kwargs.get('context', {}).get('email')}.")
        except Exception as e:
            logger.exception("Erro ao enviar email de redefinição:")
            messages.error(self.request, 'Erro ao enviar o email. Tente novamente.')


def password_reset_done_view(request: HttpRequest) -> HttpResponse:
    from django.contrib.auth.views import PasswordResetDoneView
    return PasswordResetDoneView.as_view(template_name='accounts/registration/password_reset_done.html')(request)


def password_reset_confirm_view(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    from django.contrib.auth.views import PasswordResetConfirmView
    return PasswordResetConfirmView.as_view(template_name='accounts/registration/password_reset_confirm.html')(
        request, uidb64=uidb64, token=token
    )


def password_reset_complete_view(request: HttpRequest) -> HttpResponse:
    from django.contrib.auth.views import PasswordResetCompleteView
    return PasswordResetCompleteView.as_view(template_name='accounts/registration/password_reset_complete.html')(request)


class CustomConfirmEmailView(ConfirmEmailView):
    """
    View customizada para confirmação de email.
    """
    def get(self, request: HttpRequest, key: str, *args: Any, **kwargs: Any) -> HttpResponse:
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
            return redirect('login')
        except Exception as e:
            logger.exception("Erro na confirmação de email:")
            messages.error(request, 'Erro na confirmação de email. Contate o suporte.')
            return redirect('register')
