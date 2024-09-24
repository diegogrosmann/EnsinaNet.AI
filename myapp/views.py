# myapp/views.py

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

from .utils.clientsIA import AVAILABLE_AI_CLIENTS, APIClient
from .exceptions import APIClientError, FileProcessingError
from .models import UserToken
from .forms import CustomUserCreationForm, TokenForm
from .forms import EmailAuthenticationForm
from django.contrib.auth import views as auth_views
from allauth.account.utils import send_email_confirmation
from django.core.mail import send_mail
from django.conf import settings

# Configuração do logger
logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'index.html')

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

@api_view(['POST'])
def compare(request):
    logger = logging.getLogger(__name__)
    logger.info("Iniciando a operação compare.")
    response_data = {}
    response_ias = {}

    # Verificar se o token está presente nos headers
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    token_key = auth_header.split(' ')[-1] if ' ' in auth_header else auth_header
    try:
        user_token = UserToken.objects.get(key=token_key)
        user = user_token.user
    except UserToken.DoesNotExist:
        logger.error("Token inválido.")
        return JsonResponse({"error": "Token inválido."}, status=status.HTTP_401_UNAUTHORIZED)

    # Parsing do JSON recebido
    try:
        data = request.data
        logger.debug(f"Dados recebidos!")
    except Exception as e:
        logger.error(f"Erro ao processar a requisição: {e}")
        response_data["error"] = "Erro interno ao processar a requisição."
        return JsonResponse(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Definição das configurações para cada tipo de comparação
    comparison_types = {
        'lab': {
            'required_keys': ['instructor_config', 'instructor_network', 'student_config', 'student_network'],
            'method_name': 'compare_labs'
        },
        'instruction': {
            'required_keys': ['instruction', 'student_config', 'student_network'],
            'method_name': 'compare_instruction'
        },
        'complete_comparison': {
            'required_keys': ['instruction', 'instructor_config', 'instructor_network', 'student_config', 'student_network'],
            'method_name': 'compare_complete'
        },
        # Você pode adicionar novos tipos de comparação aqui
    }

    # Identificação do tipo de comparação com base nas chaves presentes
    detected_types = []
    for comp_type, config in comparison_types.items():
        if all(key in data for key in config['required_keys']):
            detected_types.append(comp_type)

    if not detected_types:
        logger.error("Nenhum tipo de comparação detectado. Verifique as chaves do JSON.")
        response_data["error"] = "Tipo de comparação não detectado ou chaves ausentes."
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    if len(detected_types) > 1:
        logger.error("Múltiplos tipos de comparação detectados. Por favor, envie apenas um tipo por requisição.")
        response_data["error"] = "Múltiplos tipos de comparação detectados. Envie apenas um tipo por requisição."
        return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    comparison_type = detected_types[0]
    config = comparison_types[comparison_type]
    logger.info(f"Tipo de comparação detectado: {comparison_type}")

    # Iterar sobre todos os clientes de IA registrados
    for AIClientClass in AVAILABLE_AI_CLIENTS:
        ai_client_instance = AIClientClass()
        ai_client_name = ai_client_instance.name  # Usar o atributo 'name'
        try:
            with AIClientClass() as ai_client:
                method_name = config['method_name']
                compare_method = getattr(ai_client, method_name, None)
                if not compare_method:
                    logger.warning(f"O método '{method_name}' não está implementado para {ai_client_name}.")
                    response_ias[ai_client_name] = {"error": f"Método '{method_name}' não implementado."}
                    continue

                # Executar a comparação e armazenar o resultado
                result = compare_method(data)
                response_ias[ai_client_name] = result
                logger.info(f"Comparação de '{comparison_type}' com {ai_client_name} realizada com sucesso.")
        except APIClientError as e:
            logger.error(f"Erro na comparação de '{comparison_type}' com {ai_client_name}: {e}")
            response_ias[ai_client_name] = {"error": str(e)}
        except FileProcessingError as e:
            logger.error(f"Erro no processamento de arquivos para {ai_client_name}: {e}")
            response_ias[ai_client_name] = {"error": str(e)}
        except Exception as e:
            logger.error(f"Erro inesperado ao utilizar {ai_client_name}: {e}")
            response_ias[ai_client_name] = {"error": "Erro interno ao processar a requisição com " + ai_client_name}

    # Estrutura da resposta padronizada com a chave 'IAs'
    response_data['IAs'] = response_ias

    # Adicionar o tipo de comparação na resposta para contexto adicional
    response_data['comparison_type'] = comparison_type

    logger.info("Operação compare finalizada.")
    return JsonResponse(response_data, status=status.HTTP_200_OK)

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