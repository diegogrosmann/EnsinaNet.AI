"""
Formulários para registro de usuário, criação de token e autenticação.

Contém classes de formulário para registro, criação e atualização de tokens, e autenticação via email.

A documentação segue o padrão Google e os logs são gerados de forma padronizada.
"""

import logging
from typing import Any, Dict
import bleach
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model, authenticate
from allauth.account.models import EmailAddress
from django.utils.safestring import mark_safe

from accounts.models import UserToken

logger = logging.getLogger(__name__)

ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union({
    'p', 'br', 'strong', 'em', 'ul', 'ol', 'li',
    'table', 'tr', 'td', 'th', 'a', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section'
})
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """Formulário para criação de uma nova conta de usuário utilizando email como identificador único.

    Extende o UserCreationForm do Django, adaptando-o para utilizar o email como identificador principal.

    Attributes:
        email (EmailField): Campo de email obrigatório.
        password1 (CharField): Campo para senha.
        password2 (CharField): Campo para confirmação de senha.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    password1 = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Senha'})
    )
    password2 = forms.CharField(
        label='Confirme a Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirme a Senha'})
    )

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def clean_email(self) -> str:
        """Valida se o email ainda não está cadastrado.

        Returns:
            str: Email validado.

        Raises:
            ValidationError: Se o email já estiver em uso.
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            logger.warning(f"Tentativa de registro com email já cadastrado: {email}")
            raise forms.ValidationError("Usuário já cadastrado.")
        return email

    def save(self, commit=True):
        """Salva o usuário com a conta desativada até a confirmação por email.

        Args:
            commit (bool): Indica se as alterações serão salvas no banco de dados.

        Returns:
            User: Instância do usuário criado.

        Raises:
            Exception: Se houver erro ao salvar o usuário.
        """
        try:
            user = super().save(commit=False)
            user.email = self.cleaned_data['email']
            user.username = self.cleaned_data['email']
            user.is_active = False  # Desativa a conta até confirmação
            if commit:
                user.save()
                logger.info(f"Novo usuário criado: {user.email}")
            return user
        except Exception as e:
            logger.error(f"Erro ao criar usuário: {str(e)}", exc_info=True)
            raise


class TokenForm(forms.ModelForm):
    """Formulário para criação de um novo token de usuário.

    Permite ao usuário criar um novo token de API com um nome personalizado.

    Attributes:
        name (CharField): Nome do token a ser criado.
    """
    class Meta:
        model = UserToken
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do Token'
            })
        }

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário.

        Args:
            user: Usuário associado ao token.
            *args: Argumentos variáveis.
            **kwargs: Argumentos nomeados.
        """
        self.user = kwargs.pop('user', None)
        super(TokenForm, self).__init__(*args, **kwargs)

    def clean_name(self) -> str:
        """Valida se o nome do token é único para o usuário.

        Returns:
            str: Nome do token validado.

        Raises:
            ValidationError: Se já existir um token com o mesmo nome.
        """
        name = self.cleaned_data.get('name')
        if self.user and UserToken.objects.filter(user=self.user, name__iexact=name).exists():
            logger.warning(f"Tentativa de criar token com nome duplicado: {name} para usuário {self.user.email}")
            raise forms.ValidationError('Já existe um token com esse nome.')
        return name
    def save(self, commit=True):
        """Salva a instância do token atualizado.

        Args:
            commit (bool): Indica se as alterações serão salvas no banco de dados.

        Returns:
            UserToken: Instância do token atualizado.

        Raises:
            Exception: Se houver erro ao salvar o token.
        """
        try:
            token = super().save(commit=False)
            if self.user:
                token.user = self.user
            if commit:
                token.save()
                logger.info(f"Token '{token.name}' atualizado para o usuário {token.user.email}")
            return token
        except Exception as e:
            logger.error(f"Erro ao atualizar token: {str(e)}", exc_info=True)
            raise


class EmailAuthenticationForm(forms.Form):
    """Formulário para autenticação de usuário utilizando email e senha.

    Implementa a lógica de autenticação por email, verificando também se o email foi confirmado.

    Attributes:
        email (EmailField): Email do usuário.
        password (CharField): Senha do usuário.
    """
    email = forms.EmailField(
        label='Email',
        max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Senha'})
    )

    def __init__(self, request=None, *args, **kwargs):
        """Inicializa o formulário de autenticação.

        Args:
            request (HttpRequest): Objeto de requisição HTTP.
            *args: Argumentos variáveis.
            **kwargs: Argumentos nomeados.
        """
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self) -> Dict[str, Any]:
        """Valida as credenciais fornecidas no formulário.

        Returns:
            dict: Dados limpos do formulário.

        Raises:
            ValidationError: Se as credenciais forem inválidas ou o email não estiver confirmado.
        """
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            try:
                user_obj = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.warning(f"Tentativa de login com email não cadastrado: {email}")
                raise forms.ValidationError("Email ou senha inválidos.")
            except Exception as e:
                logger.error(f"Erro ao buscar usuário: {str(e)}", exc_info=True)
                raise forms.ValidationError("Erro ao processar solicitação.")

            if not user_obj.check_password(password):
                logger.warning(f"Tentativa de login com senha incorreta para: {email}")
                raise forms.ValidationError("Email ou senha inválidos.")

            try:
                email_address = EmailAddress.objects.filter(user=user_obj, email=user_obj.email).first()
                if email_address and not email_address.verified:
                    logger.info(f"Tentativa de login com email não confirmado: {email}")
                    from django.urls import reverse_lazy
                    resend_url = reverse_lazy('accounts:resend_confirmation')
                    self.add_error(None, forms.ValidationError(
                        mark_safe(
                            'Sua conta ainda não foi confirmada. '
                            f'<a href="{resend_url}?email={email}" class="btn-link">Clique aqui</a> '
                            'para reenviar o email de confirmação.'
                        )
                    ))
                    return {}
                self.user = authenticate(self.request, username=email, password=password)
                if not self.user:
                    logger.warning(f"Usuário não pôde ser autenticado: {email}")
                    raise forms.ValidationError("Não foi possível autenticar o usuário.")
                logger.info(f"Login bem-sucedido para: {email}")
            except forms.ValidationError:
                raise
            except Exception as e:
                logger.error(f"Erro durante o processo de autenticação: {str(e)}", exc_info=True)
                raise forms.ValidationError("Erro ao processar autenticação.")
        else:
            logger.warning("Tentativa de login com campos vazios")
            raise forms.ValidationError("Por favor, preencha todos os campos.")

        return self.cleaned_data

    def get_user(self):
        """Retorna o usuário autenticado.

        Returns:
            User: Usuário autenticado ou None.
        """
        return self.user


class UserTokenForm(forms.ModelForm):
    """Formulário para atualização de um token existente do usuário.

    Permite renomear um token existente.

    Attributes:
        name (CharField): Novo nome para o token.
    """
    class Meta:
        model = UserToken
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome do Token'
            })
        }

    def clean_name(self) -> str:
        """Valida se o novo nome do token é único para o usuário.

        Returns:
            str: Nome do token validado.

        Raises:
            ValidationError: Se já existir outro token com o mesmo nome.
        """
        name = self.cleaned_data.get('name')
        if UserToken.objects.filter(user=self.instance.user, name=name).exclude(id=self.instance.id).exists():
            logger.warning(f"Tentativa de renomear token para nome já existente: {name}")
            raise forms.ValidationError('Já existe um token com esse nome.')
        return name

    def save(self, commit=True):
        """Salva a instância do token atualizado.

        Args:
            commit (bool): Indica se as alterações serão salvas no banco de dados.

        Returns:
            UserToken: Instância do token atualizado.

        Raises:
            Exception: Se houver erro ao salvar o token.
        """
        try:
            token = super().save(commit=False)
            if commit:
                token.save()
                logger.info(f"Token '{token.name}' atualizado para o usuário {token.user.email}")
            return token
        except Exception as e:
            logger.error(f"Erro ao atualizar token: {str(e)}", exc_info=True)
            raise


class UserSettingsForm(forms.ModelForm):
    """Formulário para gerenciar as configurações do usuário.

    Permite ao usuário modificar seus dados pessoais e configurações de captura.

    Attributes:
        first_name (CharField): Nome do usuário.
        last_name (CharField): Sobrenome do usuário.
        email (EmailField): Email do usuário.
        capture_inactivity_timeout (IntegerField): Tempo de inatividade de captura em minutos.
    """
    first_name = forms.CharField(
        label='Nome',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label='Sobrenome',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    capture_inactivity_timeout = forms.IntegerField(
        label='Tempo de Inatividade de Captura (minutos)',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário com os valores atuais do perfil.

        Args:
            *args: Argumentos variáveis.
            **kwargs: Argumentos nomeados.
        """
        super().__init__(*args, **kwargs)
        try:
            if self.instance and hasattr(self.instance, 'profile'):
                self.fields['capture_inactivity_timeout'].initial = self.instance.profile.capture_inactivity_timeout
        except Exception as e:
            logger.error(f"Erro ao inicializar formulário de configurações: {str(e)}", exc_info=True)

    def save(self, commit=True):
        """Salva as configurações do usuário incluindo o perfil.

        Args:
            commit (bool): Indica se as alterações serão salvas no banco de dados.

        Returns:
            User: Usuário atualizado.

        Raises:
            Exception: Se houver erro ao salvar as configurações.
        """
        try:
            user = super().save(commit=False)
            if commit:
                user.save()
                if hasattr(user, 'profile'):
                    user.profile.capture_inactivity_timeout = self.cleaned_data.get('capture_inactivity_timeout')
                    user.profile.save()
                    logger.info(f"Configurações atualizadas para usuário: {user.email}")
            return user
        except Exception as e:
            logger.error(f"Erro ao salvar configurações do usuário: {str(e)}", exc_info=True)
            raise
