import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.conf import settings

from allauth.account.views import ConfirmEmailView
from allauth.account.utils import send_email_confirmation

from .forms import CustomUserCreationForm, TokenForm, EmailAuthenticationForm, UserTokenForm
from .models import UserToken, Profile
from ai_config.forms import UserAITrainingFileForm  
from ai_config.models import AITrainingFile, AIClientGlobalConfiguration

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

    all_clients = AIClientGlobalConfiguration.objects.all()
    available_ais = [(obj.api_client_class, obj.api_client_class) for obj in all_clients]

    context = {
        'tokens': UserToken.objects.filter(user=user),
        'training_files': AITrainingFile.objects.filter(user=user),
        'is_approved': user.profile.is_approved,
        'available_ais': available_ais,
        'form': TokenForm(),
        'training_file_form': UserAITrainingFileForm()
    }

    if request.method == 'POST':
        if 'create_token' in request.POST:
            form = TokenForm(request.POST, user=user)
            if form.is_valid():
                if not user.profile.is_approved:
                    messages.error(request, 'Sua conta ainda não foi aprovada pelo administrador.')
                    logger.warning(f"Usuário {user.email} tentou criar token sem aprovação.")
                    return redirect('manage_tokens')
                
                try:
                    token = form.save(commit=False)
                    token.user = user
                    token.save()
                    
                    # Configurar IAs selecionadas
                    selected_ai_types = form.cleaned_data.get('ai_types', [])
                    token.update_ai_configurations(selected_ai_types)
                    
                    logger.info(f"Token '{token.name}' criado para {user.email}")
                    messages.success(request, 'Token criado com sucesso!')
                    return redirect('manage_configurations', token_id=token.id)
                except Exception as e:
                    logger.error(f"Erro ao criar token para {user.email}: {e}")
                    messages.error(request, 'Erro ao criar o token.')
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
                    logger.error(f"Erro ao carregar arquivo de treinamento: {e}")
                    messages.error(request, 'Erro ao carregar arquivo.')
            context['training_file_form'] = training_file_form

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
        form = UserTokenForm(request.POST, request.FILES, instance=token)
        if form.is_valid():
            try:
                token = form.save()
                logger.info(f"Configurações atualizadas para token '{token.name}'")
                messages.success(request, 'Configurações atualizadas com sucesso!')
                return redirect('manage_configurations', token_id=token.id)
            except Exception as e:
                logger.error(f"Erro ao atualizar configurações: {e}")
                messages.error(request, 'Erro ao salvar as configurações.')
        else:
            logger.warning(f"Formulário inválido: {form.errors}")
            messages.error(request, 'Por favor, corrija os erros no formulário.')
    else:
        form = UserTokenForm(instance=token)

    all_clients = AIClientGlobalConfiguration.objects.all()
    available_ais = [(obj.api_client_class, obj.api_client_class) for obj in all_clients]


    return render(request, 'accounts/manage/manage_configurations.html', {
        'token': token,
        'form': form,
        'available_ais': available_ais
    })

# Classes de redefinição de senha
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

# Views de redefinição de senha
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
