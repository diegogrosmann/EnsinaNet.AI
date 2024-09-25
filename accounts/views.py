import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from allauth.account.views import ConfirmEmailView
from django.shortcuts import redirect
from django.contrib import messages
from dj_rest_auth.registration.views import VerifyEmailView
from rest_framework import status
from rest_framework.decorators import api_view

from .models import UserToken
from .forms import CustomUserCreationForm, TokenForm
from .forms import EmailAuthenticationForm
from django.contrib.auth import views as auth_views
from django.contrib.sites.shortcuts import get_current_site
from allauth.account.utils import send_email_confirmation
from django.core.mail import send_mail
from django.conf import settings

# Configuração do logger
logger = logging.getLogger(__name__)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_email_confirmation(request, user)  # Envia o email de confirmação
            messages.success(request, 'Conta criada com sucesso! Por favor, verifique seu email para ativação.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('manage_tokens')
    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)  # Não precisa especificar o backend
            messages.success(request, f'Bem-vindo, {user.email}!')
            return redirect('manage_tokens')
        else:
            # Os erros do formulário são tratados no template
            pass
    else:
        form = EmailAuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Logout realizado com sucesso!')
    return redirect('login')

@login_required
def manage_tokens(request):
    user = request.user
    tokens = UserToken.objects.filter(user=user)
    if request.method == 'POST':
        form = TokenForm(request.POST, user=user)
        if form.is_valid():
            if not user.profile.is_approved:
                messages.error(request, 'Sua conta ainda não foi aprovada pelo administrador.')
                return redirect('manage_tokens')
            token = form.save(commit=False)
            token.user = user
            token.save()
            messages.success(request, 'Token criado com sucesso!')
            return redirect('manage_tokens')
    else:
        form = TokenForm()
    context = {'tokens': tokens, 'form': form, 'is_approved': user.profile.is_approved}
    return render(request, 'manage/manage_tokens.html', context)

@login_required
def delete_token(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    if request.method == 'POST':
        token.delete()
        messages.success(request, 'Token deletado com sucesso!')
        return redirect('manage_tokens')
    return render(request, 'manage/delete_token.html', {'token': token})

class CustomPasswordResetView(auth_views.PasswordResetView):
    email_template_name = 'registration/password_reset_email.html'
    template_name = 'registration/password_reset_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_site = get_current_site(self.request)
        context['domain'] = current_site.domain
        context['site_name'] = current_site.name
        context['protocol'] = 'https' if self.request.is_secure() else 'http'
        return context

    def send_mail(self, *args, **kwargs):
        current_site = get_current_site(self.request)
        context = kwargs.get('context')
        context['domain'] = current_site.domain
        context['site_name'] = current_site.name
        context['protocol'] = 'https' if self.request.is_secure() else 'http'
        super().send_mail(*args, **kwargs)

def password_reset_view(request):
    return auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html')(request)

def password_reset_done_view(request):
    return auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html')(request)

def password_reset_confirm_view(request, uidb64, token):
    return auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html')(request, uidb64=uidb64, token=token)

def password_reset_complete_view(request):
    return auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html')(request)

class CustomConfirmEmailView(ConfirmEmailView):
    def get(self, request, key, *args, **kwargs):
        self.kwargs['key'] = key
        confirmation = self.get_object()
        # Confirma o email e ativa o usuário
        confirmation.confirm(request)

        current_site = get_current_site(request)
        user = confirmation.email_address.user
        user.is_active = True  # Ativa o usuário
        user.save()
        logger.info(f"Usuário {user.email} ativado após confirmação de email.")

        # Envia notificação ao administrador
        admin_email = settings.ADMIN_EMAIL
        subject = 'Novo Usuário Confirmado'
        message = f'O usuário "{user.email}" confirmou seu email.'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [admin_email]

        try:
            send_mail(subject, message, from_email, recipient_list)
            logger.info(f"Notificação enviada ao admin sobre o usuário que confirmou email: {user.email}")
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail para o admin: {e}")

        messages.success(request, 'Seu email foi confirmado com sucesso!')
        return redirect('login')