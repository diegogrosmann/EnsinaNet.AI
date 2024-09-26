import json
import ast

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from allauth.account.models import EmailAddress

from .models import UserToken
from .models import TokenConfiguration

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
    configurations = forms.CharField(
        label='Configurações da IA:',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Exemplo:\nmodel-name=gemini-1.5-pro\ntemperature=0.2\ntop_k=10',
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
        fields = ['api_client_class', 'configurations']

    def __init__(self, *args, **kwargs):
        super(TokenConfigurationForm, self).__init__(*args, **kwargs)
        if self.instance:
            if self.instance.configurations:
                lines = [f"{key}={value}" for key, value in self.instance.configurations.items()]
                configurations_dict = '\n'.join(lines)
            else:
                configurations_dict = ''
            self.initial['configurations'] = configurations_dict

    def clean_configurations(self):
        configurations_text = self.cleaned_data['configurations']
        configurations_dict = {}
        if configurations_text.strip() == '':
            return configurations_dict
        try:
            for line in configurations_text.strip().splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Tentar converter value para número se possível
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
        except Exception as e:
            raise forms.ValidationError('Erro ao processar as configurações: {}'.format(e))
        self.cleaned_data['configurations'] = configurations_dict
        return configurations_dict
