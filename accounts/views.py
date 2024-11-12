import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.conf import settings

from allauth.account.views import ConfirmEmailView
from allauth.account.utils import send_email_confirmation

from .forms import CustomUserCreationForm, TokenForm, EmailAuthenticationForm, TokenConfigurationForm, UserTokenForm
from .models import UserToken, TokenConfiguration


from api.utils.clientsIA import AVAILABLE_AI_CLIENTS

# Configuração do logger
logger = logging.getLogger(__name__)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                send_email_confirmation(request, user)  # Envia o email de confirmação
                logger.info(f"Novo usuário registrado: {user.email}")
                messages.success(request, 'Conta criada com sucesso! Por favor, verifique seu email para ativação.')
                return redirect('login')
            except Exception as e:
                logger.error(f"Erro ao registrar usuário: {e}")
                messages.error(request, 'Ocorreu um erro ao criar sua conta. Por favor, tente novamente.')
        else:
            logger.warning(f"Formulário de registro inválido: {form.errors}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/registration/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('manage_tokens')
    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            logger.info(f"Usuário {user.email} logado com sucesso.")
            messages.success(request, f'Bem-vindo, {user.email}!')
            return redirect('manage_tokens')
        else:
            logger.warning(f"Tentativa de login falhou: {form.errors}")
    else:
        form = EmailAuthenticationForm()
    return render(request, 'accounts/registration/login.html', {'form': form})

@login_required
def logout_view(request):
    logger.info(f"Usuário {request.user.email} fez logout.")
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
                logger.warning(f"Usuário {user.email} tentou criar token sem aprovação.")
                return redirect('manage_tokens')
            token = form.save(commit=False)
            token.user = user
            try:
                token.save()
                logger.info(f"Token '{token.name}' criado para o usuário {user.email}.")
                messages.success(request, 'Token criado com sucesso!')
                return redirect('manage_configurations', token_id=token.id)  # Redireciona para configurações
            except Exception as e:
                logger.error(f"Erro ao salvar token para o usuário {user.email}: {e}")
                messages.error(request, 'Erro ao criar o token. Por favor, tente novamente.')
        else:
            logger.warning(f"Formulário de criação de token inválido para o usuário {user.email}: {form.errors}")
    else:
        form = TokenForm()
    context = {'tokens': tokens, 'form': form, 'is_approved': user.profile.is_approved}
    return render(request, 'accounts/manage/manage_tokens.html', context)

@login_required
def delete_token(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)
    if request.method == 'POST':
        try:
            token.delete()
            logger.info(f"Token '{token.name}' deletado pelo usuário {user.email}.")
            messages.success(request, 'Token deletado com sucesso!')
            return redirect('manage_tokens')
        except Exception as e:
            logger.error(f"Erro ao deletar token para o usuário {user.email}: {e}")
            messages.error(request, 'Erro ao deletar o token. Por favor, tente novamente.')
    return render(request, 'accounts/manage/delete_token.html', {'token': token})

@login_required
def manage_configurations(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    if request.method == 'POST':
        form = UserTokenForm(request.POST, request.FILES, instance=token)  # Incluído request.FILES
        if form.is_valid():
            try:
                form.save()
                logger.info(f"Configurações atualizadas para o token '{token.name}' pelo usuário {user.email}.")
                messages.success(request, 'Configurações atualizadas com sucesso!')
                return redirect('manage_configurations', token_id=token.id)
            except Exception as e:
                logger.error(f"Erro ao salvar configurações para o token '{token.name}': {e}")
                messages.error(request, 'Erro ao salvar as configurações. Por favor, tente novamente.')
        else:
            logger.warning(f"Formulário de configuração inválido para o token '{token.name}': {form.errors}")
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        form = UserTokenForm(instance=token)

    context = {'token': token, 'form': form}
    return render(request, 'accounts/manage/manage_configurations.html', context)

class CustomPasswordResetView(auth_views.PasswordResetView):
    email_template_name = 'accounts/registration/password_reset_email.html'
    template_name = 'accounts/registration/password_reset_form.html'

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
        try:
            super().send_mail(*args, **kwargs)
            logger.info(f"E-mail de redefinição de senha enviado para {context.get('email')}.")
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail de redefinição de senha: {e}")
            messages.error(self.request, 'Erro ao enviar o e-mail. Por favor, tente novamente.')

def password_reset_view(request):
    return auth_views.PasswordResetView.as_view(template_name='accounts/registration/password_reset_form.html')(request)

def password_reset_done_view(request):
    return auth_views.PasswordResetDoneView.as_view(template_name='accounts/registration/password_reset_done.html')(request)

def password_reset_confirm_view(request, uidb64, token):
    return auth_views.PasswordResetConfirmView.as_view(template_name='accounts/registration/password_reset_confirm.html')(request, uidb64=uidb64, token=token)

def password_reset_complete_view(request):
    return auth_views.PasswordResetCompleteView.as_view(template_name='accounts/registration/password_reset_complete.html')(request)

class CustomConfirmEmailView(ConfirmEmailView):
    def get(self, request, key, *args, **kwargs):
        self.kwargs['key'] = key
        try:
            confirmation = self.get_object()
            confirmation.confirm(request)

            current_site = get_current_site(request)
            user = confirmation.email_address.user
            user.is_active = True
            user.save()
            logger.info(f"Usuário {user.email} ativado após confirmação de email.")

            # Envia notificação ao administrador
            admin_email = settings.ADMIN_EMAIL
            subject = 'Novo Usuário Confirmado'
            message = f'O usuário "{user.email}" confirmou seu email.'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [admin_email]

            send_mail(subject, message, from_email, recipient_list)
            logger.info(f"Notificação enviada ao admin sobre o usuário que confirmou email: {user.email}")

            messages.success(request, 'Seu email foi confirmado com sucesso!')
            return redirect('login')
        except Exception as e:
            logger.error(f"Erro ao confirmar email: {e}")
            messages.error(request, 'Erro ao confirmar o email. Por favor, contate o suporte.')
            return redirect('register')

@login_required
def manage_ia_configurations(request, token_id):
    user = request.user
    token = get_object_or_404(UserToken, id=token_id, user=user)

    # Obter todas as configurações de IA disponíveis para este token
    existing_configs = TokenConfiguration.objects.filter(token=token)

    # Mapear API client classes para suas configurações existentes
    existing_configs_dict = {config.api_client_class: config for config in existing_configs}

    # Criar uma lista de AI client classes para iterar nos formulários
    ai_clients = AVAILABLE_AI_CLIENTS

    if request.method == 'POST':
        # Processar cada configuração de IA
        success = True
        for ai_client in ai_clients:
            form_prefix = ai_client.name
            config_instance = existing_configs_dict.get(ai_client.name, TokenConfiguration(token=token, api_client_class=ai_client.name))
            form = TokenConfigurationForm(request.POST, prefix=form_prefix, instance=config_instance)
            if form.is_valid():
                try:
                    config = form.save(commit=False)
                    config.token = token
                    config.api_client_class = ai_client.name  # Assegura que a classe do cliente é correta
                    config.save()
                    success = success and True
                except Exception as e:
                    logger.error(f"Erro ao salvar configuração para {ai_client.name}: {e}")
                    messages.error(request, f"Erro ao salvar configuração para {ai_client.name}. Por favor, tente novamente.")
                    success = False
            else:
                logger.warning(f"Formulário inválido para {ai_client.name}: {form.errors}")
                messages.error(request, f"Erros na configuração para {ai_client.name}. Por favor, corrija os erros.")
                success = False
        if success:
            messages.success(request, 'Configurações de IA atualizadas com sucesso!')
            return redirect('manage_tokens')
    else:
        # Inicializar formulários para cada AI client
        forms = []
        for ai_client in ai_clients:
            config = existing_configs_dict.get(ai_client.name)
            form = TokenConfigurationForm(prefix=ai_client.name, instance=config)
            forms.append({
                'ai_client': ai_client.name,
                'form': form,
            })
        context = {'token': token, 'forms': forms}
        return render(request, 'accounts/manage/manage_ia_configurations.html', context)

