# accounts/forms.py

import json
import bleach
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from allauth.account.models import EmailAddress

from tinymce.widgets import TinyMCE

from .models import UserToken

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

class UserTokenForm(forms.ModelForm):
    class Meta:
        model = UserToken
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Token'})
        }

    def __init__(self, *args, **kwargs):
        super(UserTokenForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if UserToken.objects.filter(user=self.instance.user, name=name).exclude(id=self.instance.id).exists():
            raise forms.ValidationError('Já existe um token com esse nome.')
        return name