"""Formulários para registro de usuário, criação de token e autenticação.

Contém classes de formulário para registro, criação e atualização de tokens, e autenticação via email.
"""
import bleach
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model, authenticate
from allauth.account.models import EmailAddress
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from .models import UserToken
from django.utils.safestring import mark_safe

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

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Usuário já cadastrado.")
        return email

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
    """Formulário para criação de um novo token de usuário."""

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
        """Inicializa o formulário."""
        self.user = kwargs.pop('user', None)
        super(TokenForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        """Valida se o nome do token é único para o usuário.
        
        Returns:
            str: Nome do token validado.
        
        Raises:
            forms.ValidationError: Se já existir um token com o mesmo nome.
        """
        name = self.cleaned_data.get('name')
        if UserToken.objects.filter(user=self.user, name=name).exists():
            raise forms.ValidationError('Já existe um token com esse nome.')
        # Verifica se já existe um token com o mesmo nome (ignora maiúsculas/minúsculas)
        if UserToken.objects.filter(name__iexact=name).exists():
            raise ValidationError("Este nome de token já está em uso.")
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
        """Inicializa o formulário de autenticação."""
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        """Valida as credenciais fornecidas no formulário."""
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            try:
                user_obj = User.objects.get(email=email)
            except User.DoesNotExist:
                raise forms.ValidationError("Email ou senha inválidos.")

            if not user_obj.check_password(password):
                raise forms.ValidationError("Email ou senha inválidos.")

            email_address = EmailAddress.objects.filter(user=user_obj, email=user_obj.email).first()
            if email_address and not email_address.verified:
                # Modificado para usar um link simples ao invés de um form embutido
                resend_url = reverse_lazy('accounts:resend_confirmation')
                self.add_error(None, forms.ValidationError(
                    mark_safe(
                        'Sua conta ainda não foi confirmada. '
                        f'<a href="{resend_url}?email={email}" class="btn-link">Clique aqui</a> '
                        'para reenviar o email de confirmação.'
                    )
                ))
                return None

            self.user = authenticate(self.request, username=email, password=password)
        else:
            raise forms.ValidationError("Por favor, preencha todos os campos.")

        return self.cleaned_data

    def get_user(self):
        """Retorna o usuário autenticado."""
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


class UserSettingsForm(forms.ModelForm):
    """Formulário para gerenciar as configurações do usuário."""
    
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
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['capture_inactivity_timeout'].initial = self.instance.profile.capture_inactivity_timeout

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Salva o tempo de inatividade no perfil
            if hasattr(user, 'profile'):
                user.profile.capture_inactivity_timeout = self.cleaned_data.get('capture_inactivity_timeout')
                user.profile.save()
        return user
