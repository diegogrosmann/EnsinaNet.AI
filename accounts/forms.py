# accounts/forms.py

import json
import bleach
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from allauth.account.models import EmailAddress

from tinymce.widgets import TinyMCE

from .models import UserToken, TokenConfiguration, AIClientConfiguration, GlobalConfiguration

from .models import AIClientConfiguration
from api.utils.clientsIA import AVAILABLE_AI_CLIENTS

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
        original_api_key = self.initial.get('original_api_key')
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

# accounts/forms.py

class UserTokenForm(forms.ModelForm):
    base_instruction = forms.CharField(
        label='Instrução Base',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Insira a instrução base personalizada para este token. Deixe vazio para usar a configuração global.'
        }),
        required=False,
        help_text='Insira a instrução base personalizada para este token. Deixe vazio para usar a configuração global.'
    )
    prompt = forms.CharField(
        label='Prompt',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Insira o prompt personalizado para este token. Deixe vazio para usar a configuração global.'
        }),
        required=False,
        help_text='Insira o prompt personalizado para este token. Deixe vazio para usar a configuração global.'
    )
    responses = forms.CharField(
        label='Respostas',
        widget=TinyMCE(attrs={
            'class': 'tinymce', 
            'cols': 80, 
            'rows': 10
        }),
        required=False,
        help_text='Insira as respostas personalizadas para este token. Deixe vazio para usar a configuração global.'
    )
    training_file = forms.FileField(
        label='Arquivo de Treinamento',
        required=False,
        help_text='Faça upload de um arquivo txt com exemplos para treinar a IA para este token.'
    )

    class Meta:
        model = UserToken
        fields = ['base_instruction', 'prompt', 'responses', 'training_file']

    def __init__(self, *args, **kwargs):
        super(UserTokenForm, self).__init__(*args, **kwargs)

    def clean_training_file(self):
        training_file = self.cleaned_data.get('training_file')
        if training_file:
            if not training_file.name.endswith('.txt'):
                raise forms.ValidationError('O arquivo deve ser um arquivo de texto (.txt).')
            # Limitar o tamanho do arquivo 10MB
            if training_file.size > 1024 * 1024 * 10:
                raise forms.ValidationError('O arquivo de treinamento é muito grande (máximo 10MB).')
        return training_file

    def clean_base_instruction(self):
        base_instruction_html = self.cleaned_data.get('base_instruction', '').strip()
        # Sanitizar
        return bleach.clean(base_instruction_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_prompt(self):
        prompt_html = self.cleaned_data.get('prompt', '').strip()
        return bleach.clean(prompt_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_responses(self):
        responses_html = self.cleaned_data.get('responses', '').strip()
        return bleach.clean(responses_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

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

    class Meta:
        model = TokenConfiguration
        fields = ['enabled', 'model_name', 'configurations']
        widgets = {
            'configurations': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super(TokenConfigurationForm, self).__init__(*args, **kwargs)
        if self.instance:
            # Preencher as configurações existentes
            configs = self.instance.configurations or {}
            lines = [f"{key}={value}" for key, value in configs.items()]
            self.initial['configurations'] = '\n'.join(lines)
            self.initial['enabled'] = self.instance.enabled
            self.initial['model_name'] = self.instance.model_name

    def clean_configurations(self):
        configurations_text = self.cleaned_data.get('configurations')
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
                        pass
                    configurations_dict[key] = value
                else:
                    raise forms.ValidationError('Cada linha deve estar no formato key=value.')
            return configurations_dict  # Retorno correto
        else:
            return configurations_dict 

class GlobalConfigurationForm(forms.ModelForm):
    base_instruction = forms.CharField(
        label='Instrução Base Global',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'cols': 100, 
            'rows': 20,
            'placeholder': 'Insira a instrução base personalizada para este token.'
        }),
        required=False,
        help_text='Insira a instrução base global para todos os tokens.'
    )
    prompt = forms.CharField(
        label='Prompt Global',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'cols': 100, 
            'rows': 20,
            'placeholder': 'Insira o prompt personalizado para este token. Deixe vazio para usar a configuração global.'
        }),
        required=False,
        help_text='Insira o prompt global para todas as comparações.'
    )
    responses = forms.CharField(
        label='Respostas Globais',
        widget=TinyMCE(attrs={
            'class': 'tinymce', 
            'cols': 80, 
            'rows': 10
        }),
        required=False,
        help_text='Insira as respostas globais para todas as comparações. Deixe vazio para usar a configuração padrão.'
    )

    training_file = forms.FileField(
        label='Arquivo de Treinamento Global',
        required=False,
        help_text='Faça upload de um arquivo txt com exemplos para treinar a IA globalmente.'
    )
    
    class Meta:
        model = GlobalConfiguration
        fields = ['base_instruction', 'prompt', 'responses', 'training_file']
    
    def __init__(self, *args, **kwargs):
        super(GlobalConfigurationForm, self).__init__(*args, **kwargs)

    def clean_training_file(self):
        training_file = self.cleaned_data.get('training_file')
        if training_file:
            if not training_file.name.endswith('.txt'):
                raise forms.ValidationError('O arquivo deve ser um arquivo de texto (.txt).')
            # Opcional: Limitar o tamanho do arquivo (exemplo: 1MB)
            if training_file.size > 1024 * 1024:
                raise forms.ValidationError('O arquivo de treinamento é muito grande (máximo 1MB).')
        return training_file

    def clean_base_instruction(self):
        base_instruction_html = self.cleaned_data.get('base_instruction', '').strip()
        # Sanitizar
        return bleach.clean(base_instruction_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_prompt(self):
        prompt_html = self.cleaned_data.get('prompt', '').strip()
        return bleach.clean(prompt_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

    def clean_responses(self):
        responses_html = self.cleaned_data.get('responses', '').strip()
        return bleach.clean(responses_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)
