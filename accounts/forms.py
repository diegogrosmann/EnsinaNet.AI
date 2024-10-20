# accounts/forms.py

import json
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from allauth.account.models import EmailAddress

from .models import UserToken, TokenConfiguration

from .models import AIClientConfiguration
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
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
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        user.is_active = False  # Desativa a conta até a confirmação do email
        if commit:
            user.save()
        return user

class TokenForm(forms.ModelForm):
    class Meta:
        model = UserToken
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Token'})
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(TokenForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if UserToken.objects.filter(user=self.user, name=name).exists():
            raise forms.ValidationError('Já existe um token com esse nome.')
        return name

class EmailAuthenticationForm(forms.Form):
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
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user = authenticate(self.request, username=email, password=password)
            if self.user is not None:
                # Verifica se o email foi confirmado
                email_address = EmailAddress.objects.filter(user=self.user, email=self.user.email).first()
                if email_address and not email_address.verified:
                    raise forms.ValidationError('Seu email ainda não foi confirmado.')

                # Verifica se a conta está ativa
                if not self.user.is_active:
                    raise forms.ValidationError('Sua conta está inativa.')
            else:
                raise forms.ValidationError('Email ou senha inválidos.')
        else:
            raise forms.ValidationError('Por favor, preencha todos os campos.')

        return self.cleaned_data

    def get_user(self):
        return self.user

class TokenConfigurationForm(forms.ModelForm):
    enabled = forms.BooleanField(
        label='IA Habilitada',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Marque esta opção para habilitar esta IA.'
    )
    model_name = forms.CharField(
        label='Nome do Modelo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Insira o nome do modelo para esta IA.'
    )
    configurations = forms.CharField(
        label='Configurações da IA:',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Exemplo:\ntemperature=0.2\ntop_k=10',
            'title': 'Digite as configurações no formato key=value, uma por linha.'
        }),
        help_text='Insira as configurações no formato key=value, uma por linha.',
        required=False
    )
    api_client_class = forms.CharField(
        widget=forms.HiddenInput()
    )

    class Meta:
        model = TokenConfiguration
        fields = ['api_client_class', 'enabled', 'model_name', 'configurations']

    def __init__(self, *args, **kwargs):
        super(TokenConfigurationForm, self).__init__(*args, **kwargs)
        if self.instance:
            configs = self.instance.configurations or {}
            lines = [f"{key}={value}" for key, value in configs.items()]
            self.initial['configurations'] = '\n'.join(lines)
            self.initial['enabled'] = self.instance.enabled

            self.initial['model_name'] = self.instance.model_name

    def clean(self):
        cleaned_data = super().clean()

        configurations_text = cleaned_data.get('configurations')
        configurations_dict = {}
        if configurations_text.strip():
            for line in configurations_text.strip().splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass  # Mantém como string se não for número
                    configurations_dict[key] = value
                else:
                    raise forms.ValidationError('Cada linha deve estar no formato key=value.')
            cleaned_data['configurations'] = configurations_dict
        else:
            cleaned_data['configurations'] = configurations_dict
        return cleaned_data

class AIClientConfigurationForm(forms.ModelForm):
    # Cria uma lista de escolhas para api_client_class a partir de AVAILABLE_AI_CLIENTS
    API_CLIENT_CHOICES = [(client.name, client.name) for client in AVAILABLE_AI_CLIENTS]
    original_api_key = forms.CharField(widget=forms.HiddenInput(), required=False)

    api_client_class = forms.ChoiceField(
        choices=API_CLIENT_CHOICES,
        label='Classe do Cliente de API',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Selecione a classe do cliente de API.'
    )
    configurations = forms.CharField(
        label='Configurações da IA',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Exemplo:\ntemperature=0.2\ntop_k=10',
            'title': 'Digite as configurações no formato chave=valor, uma por linha.'
        }),
        help_text='Insira as configurações no formato chave=valor, uma por linha.',
        required=False
    )

    class Meta:
        model = AIClientConfiguration
        fields = ['api_client_class', 'api_key', 'model_name', 'configurations']
        widgets = {
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chave da API'}),
            'model_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Modelo'}),
        }

    def __init__(self, *args, **kwargs):
        super(AIClientConfigurationForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.api_key:
            masked_key = self.mask_api_key(self.instance.api_key)
            self.initial['api_key'] = masked_key
            self.initial['original_api_key'] = self.instance.api_key
        if self.instance and self.instance.configurations:
            # Converte o dicionário de configurações em linhas chave=valor
            configs = self.instance.configurations
            lines = [f"{key}={value}" for key, value in configs.items()]
            self.initial['configurations'] = '\n'.join(lines)
        else:
            self.initial['configurations'] = ''

    def mask_api_key(self, api_key):
        if len(api_key) > 8:
            return f"{api_key[:4]}****{api_key[-4:]}"
        else:
            return '*' * len(api_key)

    def clean_api_key(self):
        api_key = self.cleaned_data.get('api_key')
        original_api_key = self.initial['original_api_key']
        masked_key = self.mask_api_key(original_api_key) if original_api_key else ''
        
        if api_key == masked_key:
            # API Key não foi alterada
            return original_api_key
        else:
            # API Key foi alterada; validar conforme necessário
            return api_key

    def clean_configurations(self):
        configurations_text = self.cleaned_data.get('configurations', '')
        configurations_dict = {}
        if configurations_text.strip():
            for line in configurations_text.strip().splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Tenta converter para float ou int, senão mantém como string
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                    configurations_dict[key] = value
                else:
                    raise forms.ValidationError('Cada linha deve estar no formato chave=valor.')
            return configurations_dict
        return {}
    
    def clean_api_client_class(self):
        api_client_class = self.cleaned_data.get('api_client_class')
        if AIClientConfiguration.objects.filter(api_client_class=api_client_class).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Já existe uma configuração para esta classe de cliente de API.')
        return api_client_class