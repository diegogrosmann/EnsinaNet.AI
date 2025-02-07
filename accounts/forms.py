"""Formulários para registro de usuário, criação de token e autenticação.

Contém classes de formulário para registro, criação e atualização de tokens, e autenticação via email.
"""

import json
import bleach
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model, authenticate
from allauth.account.models import EmailAddress

from tinymce.widgets import TinyMCE

from .models import UserToken
from ai_config.models import AIClientGlobalConfiguration

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
    """Formulário para criação de uma nova conta de usuário utilizando email como identificador único."""

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

    def save(self, commit=True):
        """Salva o usuário com a conta desativada até a confirmação por email.
        
        Argumentos:
            commit (bool): Indica se as alterações serão salvas no banco de dados.
        
        Retorna:
            User: Instância do usuário criado.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        user.is_active = False  # Desativa a conta até confirmação
        if commit:
            user.save()
        return user


class TokenForm(forms.ModelForm):
    """Formulário para criação de um novo token de usuário e seleção de tipos de IA."""

    class Meta:
        model = UserToken
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Token'})
        }

    def __init__(self, *args, **kwargs):
        """Inicializa o formulário adicionando o campo de tipos de IA.
        
        Argumentos:
            user: Instância do usuário associado ao token.
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        self.user = kwargs.pop('user', None)
        super(TokenForm, self).__init__(*args, **kwargs)

        all_clients = AIClientGlobalConfiguration.objects.all()
        choices = [(client.api_client_class, client.api_client_class) for client in all_clients]

        self.fields['ai_types'] = forms.MultipleChoiceField(
            choices=choices,
            required=False,
            widget=forms.CheckboxSelectMultiple
        )

    def clean_name(self):
        """Valida se o nome do token é único para o usuário.
        
        Retorna:
            str: Nome do token validado.
        
        Levanta:
            forms.ValidationError: Se já existir um token com o mesmo nome.
        """
        name = self.cleaned_data.get('name')
        if UserToken.objects.filter(user=self.user, name=name).exists():
            raise forms.ValidationError('Já existe um token com esse nome.')
        return name


class EmailAuthenticationForm(forms.Form):
    """Formulário para autenticação de usuário utilizando email e senha."""

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
        
        Argumentos:
            request (HttpRequest): Objeto da requisição HTTP.
            *args: Argumentos posicionais.
            **kwargs: Argumentos nomeados.
        """
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        """Valida as credenciais fornecidas no formulário.
        
        Retorna:
            dict: Dados limpos do formulário.
        
        Levanta:
            forms.ValidationError: Se as credenciais estiverem ausentes ou inválidas.
        """
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user = authenticate(self.request, username=email, password=password)
            if self.user is not None:
                email_address = EmailAddress.objects.filter(user=self.user, email=self.user.email).first()
                if email_address and not email_address.verified:
                    raise forms.ValidationError('Seu email ainda não foi confirmado.')
                if not self.user.is_active:
                    raise forms.ValidationError('Sua conta está inativa.')
            else:
                raise forms.ValidationError('Email ou senha inválidos.')
        else:
            raise forms.ValidationError('Por favor, preencha todos os campos.')

        return self.cleaned_data

    def get_user(self):
        """Retorna o usuário autenticado.
        
        Retorna:
            User: Usuário autenticado.
        """
        return self.user


class UserTokenForm(forms.ModelForm):
    """Formulário para atualização de um token existente do usuário."""

    class Meta:
        model = UserToken
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Token'})
        }

    def clean_name(self):
        """Valida se o novo nome do token é único para o usuário.
        
        Retorna:
            str: Nome do token validado.
        
        Levanta:
            forms.ValidationError: Se já existir outro token com o mesmo nome.
        """
        name = self.cleaned_data.get('name')
        if UserToken.objects.filter(user=self.instance.user, name=name).exclude(id=self.instance.id).exists():
            raise forms.ValidationError('Já existe um token com esse nome.')
        return name

    def save(self, commit=True):
        """Salva a instância do token atualizado.
        
        Argumentos:
            commit (bool): Indica se as alterações serão salvas no banco de dados.
        
        Retorna:
            UserToken: Instância do token atualizado.
        """
        token = super().save(commit=False)
        if commit:
            token.save()
        return token
