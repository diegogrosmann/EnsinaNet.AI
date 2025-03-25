# accounts/tests/test_forms.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.forms import (
    CustomUserCreationForm,
    TokenForm,
    EmailAuthenticationForm,
    UserTokenForm,
    UserSettingsForm,
)
from accounts.models import UserToken, Profile

User = get_user_model()

class CustomUserCreationFormTest(TestCase):
    """Testes para o formulário CustomUserCreationForm."""

    def test_form_valido_cria_usuario_inativo(self):
        """
        Testa se o formulário válido cria um usuário inativo.

        Verifica se o usuário é criado com is_active=False e se o email é definido corretamente.
        """
        form_data = {
            "email": "newuser@example.com",
            "password1": "teste1234",
            "password2": "teste1234",
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())
        user = form.save(commit=True)
        self.assertEqual(user.email, "newuser@example.com")
        self.assertFalse(user.is_active)

    def test_form_invalido_email_duplicado(self):
        """
        Testa se o formulário invalida email já existente.

        Verifica se a validação falha para usuário duplicado.
        """
        User.objects.create_user(email="dup@example.com", username="dup@example.com", password="test123")
        form_data = {
            "email": "dup@example.com",
            "password1": "teste1234",
            "password2": "teste1234",
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("Usuário já cadastrado.", form.errors["email"])


class TokenFormTest(TestCase):
    """Testes para o formulário TokenForm."""

    def setUp(self):
        """Cria um usuário para associar ao token."""
        self.user = User.objects.create_user(
            username="tokenform@example.com",
            email="tokenform@example.com",
            password="test123"
        )

    def test_form_valido_cria_token(self):
        """
        Testa se o formulário válido cria o token corretamente.

        Verifica se o token é salvo com o nome especificado.
        """
        form_data = {"name": "Meu Token"}
        form = TokenForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
        token = form.save(commit=True)
        self.assertEqual(token.name, "Meu Token")
        self.assertEqual(token.user, self.user)

    def test_form_invalido_nome_duplicado(self):
        """
        Testa se o formulário inválida nome de token duplicado.

        Verifica se o formulário falha ao criar token com mesmo nome para o mesmo usuário.
        """
        UserToken.objects.create(user=self.user, name="Meu Token", key="abc123")
        form_data = {"name": "Meu Token"}
        form = TokenForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um token com esse nome.", form.errors["name"])


class EmailAuthenticationFormTest(TestCase):
    """Testes para o formulário EmailAuthenticationForm."""

    def setUp(self):
        """Cria um usuário para teste de login."""
        self.user = User.objects.create_user(
            email="auth@example.com",
            username="auth@example.com",
            password="test123"
        )

    def test_form_valido_autentica_usuario(self):
        """
        Testa se o formulário válido autentica o usuário.

        Verifica se o método get_user() retorna o usuário correto.
        """
        form_data = {
            "email": "auth@example.com",
            "password": "test123",
        }
        form = EmailAuthenticationForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user(), self.user)

    def test_form_invalido_senha_errada(self):
        """
        Testa se o formulário não autentica com senha incorreta.

        Verifica se 'is_valid()' falha e retorna erro adequado.
        """
        form_data = {
            "email": "auth@example.com",
            "password": "wrongpass",
        }
        form = EmailAuthenticationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("Email ou senha inválidos.", form.errors["__all__"])


class UserTokenFormTest(TestCase):
    """Testes para o formulário UserTokenForm (editar token)."""

    def setUp(self):
        """Cria um usuário e um token."""
        self.user = User.objects.create_user(
            email="usertokenform@example.com",
            username="usertokenform@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(
            user=self.user,
            name="Token Antigo",
            key="some-key-12345"
        )

    def test_form_valido_altera_nome(self):
        """
        Testa se o formulário altera o nome do token corretamente.

        Verifica se o novo nome é salvo no objeto.
        """
        form_data = {"name": "Token Novo"}
        form = UserTokenForm(data=form_data, instance=self.token)
        self.assertTrue(form.is_valid())
        updated_token = form.save(commit=True)
        self.assertEqual(updated_token.name, "Token Novo")

    def test_form_invalido_nome_duplicado(self):
        """
        Testa se o formulário falha ao alterar para um nome que já existe no mesmo usuário.
        """
        UserToken.objects.create(user=self.user, name="Token Novo", key="another-key-123")
        form_data = {"name": "Token Novo"}
        form = UserTokenForm(data=form_data, instance=self.token)
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe um token com esse nome.", form.errors["name"])


class UserSettingsFormTest(TestCase):
    """Testes para o formulário UserSettingsForm."""

    def setUp(self):
        """Cria um usuário com profile."""
        self.user = User.objects.create_user(
            email="settings@example.com",
            username="settings@example.com",
            password="test123"
        )
        Profile.objects.get_or_create(user=self.user)

    def test_form_valido_atualiza_dados(self):
        """
        Testa se o formulário válido atualiza as informações de usuário e profile.

        Verifica se o first_name, last_name e capture_inactivity_timeout são salvos.
        """
        form_data = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "email": "settings@example.com",
            "capture_inactivity_timeout": 20
        }
        form = UserSettingsForm(data=form_data, instance=self.user)
        self.assertTrue(form.is_valid())
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Nome")
        self.assertEqual(self.user.last_name, "Sobrenome")
        self.assertEqual(self.user.profile.capture_inactivity_timeout, 20)
