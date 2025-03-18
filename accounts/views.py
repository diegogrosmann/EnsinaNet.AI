"""
Views para a aplicação accounts.

Este módulo contém funções e classes que gerenciam o registro, login, logout,
gerenciamento de tokens, configuração, redefinição de senha e confirmação de email.
"""

import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout, get_user_model, login
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.safestring import mark_safe
from django.db import transaction
from django.views import View

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
from core.types import APPResponse

logger = logging.getLogger(__name__)
User = get_user_model()

### Autenticação e Registro ###

def auth_register(request: HttpRequest) -> HttpResponse:
    """Registra um novo usuário e envia email de confirmação.

    Cria uma nova conta de usuário e envia um email para confirmação.
    A conta permanece inativa até a confirmação do email.

    Args:
        request: Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada ou redirecionamento para a página de login.
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    send_email_confirmation(request, user)
                logger.info(f"Usuário registrado com sucesso: {user.email}")
                messages.success(request, 'Conta criada com sucesso! Verifique seu email para confirmação.')
                return redirect('accounts:login')
            except Exception as e:
                logger.exception(f"Erro durante registro de usuário: {e}")
                messages.error(request, 'Erro ao criar a conta. Tente novamente.')
        else:
            logger.warning(f"Tentativa de registro com dados inválidos: {form.errors}")
    else:
        form = CustomUserCreationForm()
        logger.debug("Formulário de registro exibido")
    
    return render(request, 'accounts/registration/register.html', {'form': form})


def auth_login(request: HttpRequest) -> HttpResponse:
    """Realiza autenticação e login do usuário.

    Processa o formulário de login e redireciona o usuário.
    Se o usuário já estiver logado, redireciona para 'tokens_manage'.

    Args:
        request: Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada ou redirecionamento após login.
    """
    if request.user.is_authenticated:
        logger.debug(f"Usuário já autenticado: {request.user.email}")
        return redirect('accounts:tokens_manage')

    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        try:
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                logger.info(f"Login bem-sucedido para usuário: {user.email}")
                return redirect('accounts:tokens_manage')
            else:
                logger.warning(f"Tentativa de login inválida: {form.errors}")
                # As mensagens de erro já estão sendo geradas pelo form.clean()
                messages.error(request, form.errors.get('__all__', 'Email ou senha inválidos.'))
                return redirect('accounts:login')
        except Exception as e:
            logger.error(f"Erro durante processamento de login: {e}")
            messages.error(request, 'Ocorreu um erro durante o login. Tente novamente.')
            return redirect('accounts:login')
    else:
        form = EmailAuthenticationForm()
        logger.debug("Formulário de login exibido")
    
    return render(request, 'accounts/registration/login.html', {'form': form})


@login_required
def auth_logout(request: HttpRequest) -> HttpResponse:
    """Realiza o logout do usuário atual.

    Encerra a sessão do usuário e redireciona para a página de login.

    Args:
        request: Objeto de requisição HTTP.

    Returns:
        HttpResponse: Redirecionamento para a página de login.
    """
    try:
        user_email = request.user.email
        logout(request)
        logger.info(f"Logout realizado com sucesso: {user_email}")
        messages.success(request, 'Logout realizado com sucesso!')
    except Exception as e:
        logger.error(f"Erro durante logout: {e}")
        messages.error(request, 'Ocorreu um erro durante o logout.')
    
    return redirect('accounts:login')


def auth_resend_confirmation(request: HttpRequest) -> HttpResponse:
    """Reenvia o email de confirmação para o usuário informado.
    
    Permite que usuários não confirmados solicitem um novo email de confirmação.
    Não requer autenticação, apenas email e senha válidos.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        HttpResponse: Página renderizada ou redirecionamento após o envio.
    """
    # Pré-preenche o email se fornecido via GET
    initial_email = request.GET.get('email', '')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            # Verifica se o usuário existe
            user = User.objects.get(email=email)
            
            # Verifica se a senha está correta
            if user.check_password(password):
                # Verifica se o email já foi confirmado
                email_address = EmailAddress.objects.filter(user=user, email=email).first()
                
                if email_address and not email_address.verified:
                    send_email_confirmation(request, user)
                    logger.info(f"Email de confirmação reenviado para: {email}")
                    messages.success(request, 'Email de confirmação reenviado com sucesso.')
                else:
                    logger.info(f"Tentativa de reenvio para email já confirmado: {email}")
                    messages.info(request, 'Este email já foi confirmado.')
            else:
                logger.warning(f"Tentativa de reenvio com senha incorreta: {email}")
                messages.error(request, 'Credenciais inválidas.')
                return redirect('accounts:resend_confirmation')
        except User.DoesNotExist:
            logger.warning(f"Tentativa de reenvio para email não cadastrado: {email}")
            messages.error(request, 'Credenciais inválidas.')
            return redirect('accounts:resend_confirmation')
        except Exception as e:
            logger.error(f"Erro ao reenviar email de confirmação para {email}: {e}")
            messages.error(request, 'Ocorreu um erro ao processar sua solicitação.')
            return redirect('accounts:resend_confirmation')
        
        return redirect('accounts:login')
    
    logger.debug("Formulário de reenvio de confirmação exibido")
    return render(request, 'accounts/registration/resend_confirmation.html', {
        'initial_email': initial_email
    })


### Redefinição de Senha ###

class CustomPasswordResetView(PasswordResetView):
    """View customizada para redefinição de senha.
    
    Estende a PasswordResetView padrão do Django para adicionar
    logs e tratamento de erros personalizado.

    Attributes:
        template_name: Caminho do template para o formulário de reset de senha.
        email_template_name: Caminho do template utilizado no envio do email.
    """

    template_name = 'accounts/registration/password_reset_form.html'
    html_email_template_name = 'accounts/registration/password_reset_email.html'

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Retorna o contexto atualizado com informações do site.
        
        Args:
            **kwargs: Argumentos adicionais para o contexto.
            
        Returns:
            Dict[str, Any]: Contexto atualizado com informações do site.
        """
        context = super().get_context_data(**kwargs)
        try:
            current_site = get_current_site(self.request)
            context.update({
                'domain': current_site.domain,
                'site_name': current_site.name,
                'protocol': 'https' if self.request.is_secure() else 'http',
            })
            logger.debug(f"Contexto de redefinição de senha preparado para: {current_site.domain}")
        except Exception as e:
            logger.error(f"Erro ao preparar contexto para redefinição de senha: {e}")
        return context

    def form_valid(self, form):
        """Processa o formulário válido de redefinição de senha.
        
        Args:
            form: Formulário validado.
            
        Returns:
            HttpResponse: Resposta HTTP após processamento.
        """
        try:
            email = form.cleaned_data.get("email", "")
            logger.info(f"Solicitação de redefinição de senha para: {email}")
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Erro ao processar redefinição de senha: {e}")
            messages.error(self.request, 'Ocorreu um erro ao processar sua solicitação.')
            return self.render_to_response(self.get_context_data(form=form))

    def send_mail(self, *args: Any, **kwargs: Any) -> None:
        """Envia o email de redefinição de senha e registra o log da operação.
        
        Args:
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        try:
            super().send_mail(*args, **kwargs)
            email = kwargs.get('context', {}).get('email', 'desconhecido')
            logger.info(f"E-mail de redefinição enviado para {email}.")
        except Exception as e:
            logger.exception(f"Erro ao enviar email de redefinição: {e}")
            messages.error(self.request, 'Erro ao enviar o email de redefinição.')


def password_reset_done(request: HttpRequest) -> HttpResponse:
    """Exibe a página de confirmação após solicitar o reset de senha.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        HttpResponse: Página de confirmação de solicitação enviada.
    """
    from django.contrib.auth.views import PasswordResetDoneView
    
    logger.debug("Exibindo página de confirmação de reset de senha")
    return PasswordResetDoneView.as_view(
        template_name='accounts/registration/password_reset_done.html'
    )(request)


def password_reset_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Exibe a página para confirmação do reset de senha.
    
    Args:
        request: Objeto de requisição HTTP.
        uidb64: ID do usuário codificado.
        token: Token de segurança.
        
    Returns:
        HttpResponse: Página para definição de nova senha.
    """
    from django.contrib.auth.views import PasswordResetConfirmView
    
    try:
        logger.debug(f"Processando confirmação de reset de senha, token: {token[:8]}...")
        return PasswordResetConfirmView.as_view(
            template_name='accounts/registration/password_reset_confirm.html'
        )(request, uidb64=uidb64, token=token)
    except Exception as e:
        logger.error(f"Erro ao processar confirmação de reset de senha: {e}")
        messages.error(request, 'Link de redefinição de senha inválido ou expirado.')
        return redirect('accounts:login')


def password_reset_complete(request: HttpRequest) -> HttpResponse:
    """Exibe a página informando a conclusão do reset de senha.
    
    Args:
        request: Objeto de requisição HTTP.
        
    Returns:
        HttpResponse: Página de conclusão do processo.
    """
    from django.contrib.auth.views import PasswordResetCompleteView
    
    logger.debug("Exibindo página de reset de senha concluído")
    return PasswordResetCompleteView.as_view(
        template_name='accounts/registration/password_reset_complete.html'
    )(request)


### Confirmação de Email ###

class CustomConfirmEmailView(ConfirmEmailView):
    """View customizada para confirmação de email.

    Esta view personaliza o processo de confirmação de email, ativando o usuário
    e enviando notificação para o administrador.
    """

    def get(self, request: HttpRequest, key: str, *args: Any, **kwargs: Any) -> HttpResponse:
        """Realiza a confirmação do email e ativa o usuário.
        
        Args:
            request: Objeto de requisição HTTP.
            key: Chave de confirmação do email.
            *args: Argumentos posicionais adicionais.
            **kwargs: Argumentos nomeados adicionais.
            
        Returns:
            HttpResponse: Redirecionamento após confirmar o email.
        """
        self.kwargs['key'] = key
        try:
            # Confirma o email
            confirmation = self.get_object()
            confirmation.confirm(request)
            user = confirmation.email_address.user
            
            # Ativa o usuário
            user.is_active = True
            user.save()
            logger.info(f"Email confirmado e usuário ativado: {user.email}")
            
            # Notifica o administrador
            try:
                # Prepara o contexto para o email
                current_site = get_current_site(request)
                context = {
                    'user': user,
                    'confirmation_date': datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'current_site': current_site
                }
                
                # Renderiza o email HTML
                email_html = render_to_string('account/email/user_confirmed_email.html', context)
                
                admin_email = getattr(settings, 'ADMIN_EMAIL', None)
                if admin_email:
                    subject = 'Novo Usuário Confirmado'
                    message = f'O usuário "{user.email}" confirmou seu email.'
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [admin_email], html_message=email_html)
                    logger.info(f"Notificação enviada ao administrador sobre confirmação: {user.email}")
                else:
                    logger.warning("ADMIN_EMAIL não configurado em settings")
            except Exception as e:
                # Não falha o processo se a notificação ao admin falhar
                logger.error(f"Erro ao enviar notificação ao administrador: {e}")
            
            messages.success(request, 'Email confirmado com sucesso! Você já pode fazer login.')
            return redirect('accounts:login')
            
        except Exception as e:
            logger.exception(f"Erro na confirmação de email: {e}")
            messages.error(request, 'Erro na confirmação de email. Contate o suporte.')
            return redirect('accounts:register')


### Gerenciamento de Tokens ###

@login_required
def tokens_manage(request: HttpRequest) -> HttpResponse:
    """Gerencia tokens do usuário.
    
    Exibe a lista de tokens do usuário atual e fornece opções
    para criar, editar e excluir tokens.

    Args:
        request: Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada com o contexto atualizado.
    """
    try:
        user = request.user
        tokens = UserToken.objects.filter(user=user)
        
        # Lista de configurações globais de IA disponíveis
        available_ais = [
            (obj.api_client_class, obj.api_client_class)
            for obj in AIClientGlobalConfiguration.objects.all()
        ]
        
        logger.debug(f"Exibindo tokens ({tokens.count()}) para o usuário: {user.email}")
        
        context = {
            'tokens': tokens,
            'is_approved': user.profile.is_approved,
            'available_ais': available_ais,
            'form': TokenForm(),
        }
        return render(request, 'accounts/manage/tokens_manage.html', context)
    except Exception as e:
        logger.error(f"Erro ao carregar página de gerenciamento de tokens: {e}")
        messages.error(request, 'Ocorreu um erro ao carregar seus tokens.')
        return render(request, 'accounts/manage/tokens_manage.html', {'tokens': [], 'form': TokenForm()})


@login_required
def token_create(request: HttpRequest) -> HttpResponse:
    """Cria um novo token para o usuário.
    
    Processa o formulário de criação de token e valida antes de salvar.
    Suporta requisições AJAX e normais.

    Args:
        request: Objeto de requisição HTTP.

    Returns:
        HttpResponse: Redirecionamento ou resposta HTTP apropriada.
    """
    if request.method != 'POST':
        logger.warning("Tentativa de criar token com método não-POST")
        return redirect('accounts:tokens_manage')

    user = request.user
    form = TokenForm(request.POST, user=user)
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Validação do formulário
    if not form.is_valid():
        if is_ajax:
            # Formato consistente para erros
            errors = {}
            for field, error_messages in form.errors.items():
                errors[field] = [str(msg) for msg in error_messages]
            
            logger.debug(f"Erros de validação do token (AJAX): {errors}")
            
            response = APPResponse(
                success=False,
                error='Formulário inválido',
                data={'errors': form.errors}
            )
            return JsonResponse(response.to_dict(), status=400)
        
        logger.warning(f"Validação falhou na criação do token: {form.errors}")
        messages.error(request, 'Formulário inválido.')
        return redirect('accounts:tokens_manage')

    # Verificação de aprovação
    if not user.profile.is_approved:
        if is_ajax:
            logger.warning(f"Tentativa de criação de token sem aprovação (AJAX): {user.email}")
            return JsonResponse({
                'success': False, 
                'errors': {'__all__': ['Sua conta não foi aprovada.']}
            }, status=403)
        
        logger.warning(f"Tentativa de criação de token sem aprovação: {user.email}")
        messages.error(request, 'Sua conta não foi aprovada.')
        return redirect('accounts:tokens_manage')

    # Criação do token
    try:
        token = form.save(commit=False)
        token.user = user
        token.save()
        logger.info(f"Token criado com sucesso: {token.name} ({token.id}) para {user.email}")
        
        if is_ajax:
            response = APPResponse(
                success=True,
                data={
                    'message': 'Token criado com sucesso!',
                    'token_id': str(token.id)
                }
            )
            return JsonResponse(response.to_dict())
            
        messages.success(request, 'Token criado com sucesso!')
        return redirect('accounts:token_config', token_id=token.id)
    except Exception as e:
        logger.exception(f"Erro ao criar token para {user.email}: {e}")
        
        if is_ajax:
            return JsonResponse({
                'success': False, 
                'errors': {'__all__': [f'Erro ao criar token: {str(e)}']}
            }, status=500)
            
        messages.error(request, 'Erro ao criar token.')
        return redirect('accounts:tokens_manage')


@login_required
def token_delete(request: HttpRequest, token_id: str) -> HttpResponse:
    """Exclui um token do usuário.
    
    Processa a solicitação de exclusão de token e responde
    adequadamente para requisições AJAX.
    
    Args:
        request: Objeto de requisição HTTP.
        token_id: ID do token a ser excluído.
        
    Returns:
        HttpResponse: Redirecionamento ou resposta JSON apropriada.
    """
    try:
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        
        if request.method == 'POST':
            try:
                token_name = token.name
                user_email = token.user.email
                token.delete()
                logger.info(f"Token excluído com sucesso: {token_name} por {user_email}")
                messages.success(request, 'Token excluído com sucesso!')

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    response = APPResponse(
                        success=True,
                        data={'message': 'Token excluído com sucesso!'}
                    )
                    return JsonResponse(response.to_dict())
                
                return redirect('accounts:tokens_manage')
            except Exception as e:
                logger.exception(f"Erro ao excluir token {token.name}: {e}")
                messages.error(request, f'Erro ao excluir token: {str(e)}')
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)}, status=500)

        logger.debug(f"Exibindo página de confirmação para exclusão do token: {token.name}")
        return render(request, 'accounts/manage/delete_token.html', {'token': token})
    except Exception as e:
        logger.error(f"Erro ao processar solicitação de exclusão de token: {e}")
        messages.error(request, 'Erro ao processar solicitação de exclusão.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=404)
            
        return redirect('accounts:tokens_manage')


@login_required
def token_edit_name(request: HttpRequest, token_id: str) -> HttpResponse:
    """Atualiza o nome de um token.
    
    Args:
        request: Objeto de requisição HTTP.
        token_id: ID do token a ser editado.
        
    Returns:
        HttpResponse: Redirecionamento após atualização.
    """
    try:
        token = get_object_or_404(UserToken, id=token_id, user=request.user)
        
        if request.method == 'POST':
            new_name = request.POST.get('name')
            
            if new_name and new_name != token.name:
                try:
                    old_name = token.name
                    token.name = new_name
                    token.save()
                    logger.info(f"Nome do token alterado: '{old_name}' para '{new_name}' (ID: {token_id})")
                    messages.success(request, 'Nome do token atualizado com sucesso!')
                except Exception as e:
                    logger.error(f"Erro ao atualizar nome do token {token_id}: {e}")
                    messages.error(request, f'Erro ao atualizar nome do token: {str(e)}')
            else:
                logger.debug(f"Nome do token não foi alterado ou estava vazio: {token.name}")
                
        return redirect('accounts:token_config', token_id=token_id)
    except Exception as e:
        logger.error(f"Erro ao processar edição de nome do token: {e}")
        messages.error(request, 'Erro ao processar solicitação de edição.')
        return redirect('accounts:tokens_manage')


@login_required
def token_config(request: HttpRequest, token_id: str) -> HttpResponse:
    """Gerencia as configurações específicas de um token.
    
    Permite configurar parâmetros específicos para um token.

    Args:
        request: Objeto de requisição HTTP.
        token_id: Identificador do token a ser configurado.

    Returns:
        HttpResponse: Página renderizada com as configurações atualizadas.
    """
    try:
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
                    logger.exception(f"Erro ao atualizar configurações do token {token.name}: {e}")
                    messages.error(request, f'Erro ao salvar configurações: {str(e)}')
            else:
                logger.warning(f"Formulário inválido para token {token_id}: {form.errors}")
                messages.error(request, 'Corrija os erros no formulário.')
        else:
            form = UserTokenForm(instance=token)
            logger.debug(f"Exibindo configurações para token: {token.name}")
            
        available_ais = [
            (obj.api_client_class, obj.api_client_class)
            for obj in AIClientGlobalConfiguration.objects.all()
        ]
        
        context = {
            'token': token,
            'form': form,
            'available_ais': available_ais,
        }
        return render(request, 'accounts/manage/token_config.html', context)
    except Exception as e:
        logger.error(f"Erro ao acessar configurações do token: {e}")
        messages.error(request, 'Erro ao carregar configurações do token.')
        return redirect('accounts:tokens_manage')


### Configurações do Usuário ###

@login_required
def user_settings(request: HttpRequest) -> HttpResponse:
    """Gerencia as configurações do usuário.
    
    Permite ao usuário atualizar seus dados pessoais e outras configurações.

    Args:
        request: Objeto de requisição HTTP.

    Returns:
        HttpResponse: Página renderizada com o formulário de configurações do usuário.
    """
    user = request.user
    
    try:
        # Garante que existe um profile
        Profile.objects.get_or_create(user=user)
        
        if request.method == 'POST':
            form = UserSettingsForm(request.POST, instance=user)
            if form.is_valid():
                try:
                    form.save()
                    logger.info(f"Configurações atualizadas para usuário: {user.email}")
                    messages.success(request, 'Configurações atualizadas com sucesso!')
                    return redirect('accounts:user_settings')
                except Exception as e:
                    logger.exception(f"Erro ao salvar configurações do usuário {user.email}: {e}")
                    messages.error(request, f'Erro ao atualizar configurações: {str(e)}')
            else:
                logger.warning(f"Formulário de configurações inválido para {user.email}: {form.errors}")
                messages.error(request, 'Erro ao atualizar configurações. Verifique os dados informados.')
        else:
            form = UserSettingsForm(instance=user)
            logger.debug(f"Exibindo configurações para usuário: {user.email}")
        
        context = {
            'form': form,
        }
        return render(request, 'accounts/settings/user.html', context)
    except Exception as e:
        logger.error(f"Erro ao acessar configurações do usuário {user.email}: {e}")
        messages.error(request, 'Ocorreu um erro ao carregar suas configurações.')
        # Tenta criar um formulário mesmo com erro
        form = UserSettingsForm(instance=user)
        return render(request, 'accounts/settings/user.html', {'form': form})