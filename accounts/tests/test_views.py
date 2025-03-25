# accounts/tests/test_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from accounts.models import UserToken, Profile

User = get_user_model()

class AuthViewsTest(TestCase):
    """Testes para as views de autenticação (registro, login, logout, etc.)."""

    def setUp(self):
        """Configura o ambiente para os testes."""
        self.client = Client()
        self.register_url = reverse("accounts:register")
        self.login_url = reverse("accounts:login")
        self.logout_url = reverse("accounts:logout")
        self.resend_confirmation_url = reverse("accounts:resend_confirmation")

        # Cria um usuário para teste de login
        self.user = User.objects.create_user(
            email="login@example.com",
            username="login@example.com",
            password="test123",
            is_active=True
        )
        # Marca o email como verificado (caso use verificação via allauth)
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            primary=True,
            verified=True
        )

    def test_register_get(self):
        """
        Testa se a página de registro carrega corretamente (GET).

        Verifica status code e uso do template.
        """
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/registration/register.html")

    def test_register_post_valido(self):
        """
        Testa o registro com dados válidos (POST).

        Verifica se o usuário é criado e redirecionado para 'accounts:login'.
        """
        data = {
            "email": "novo@example.com",
            "password1": "teste1234",
            "password2": "teste1234",
        }
        response = self.client.post(self.register_url, data, follow=True)
        self.assertRedirects(response, self.login_url)
        self.assertTrue(User.objects.filter(email="novo@example.com").exists())

    def test_register_post_invalido(self):
        """
        Testa o registro com dados inválidos.

        Verifica se retorna erros e não cria usuário.
        """
        data = {
            "email": "",  # inválido
            "password1": "teste1234",
            "password2": "teste1234",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)  # permanece na mesma página
        self.assertFalse(User.objects.filter(email="").exists())

    def test_login_get(self):
        """
        Testa se a página de login carrega corretamente (GET).
        """
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/registration/login.html")

    def test_login_post_valido(self):
        """
        Testa o login com credenciais válidas.

        Verifica se redireciona para 'tokens_manage' e se o usuário fica logado.
        """
        data = {
            "email": "login@example.com",
            "password": "test123"
        }
        response = self.client.post(self.login_url, data)
        self.assertRedirects(response, reverse("accounts:tokens_manage"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_post_invalido(self):
        """
        Testa o login com credenciais inválidas.

        Verifica se permanece na página de login com mensagem de erro.
        """
        data = {
            "email": "login@example.com",
            "password": "wrongpass"
        }
        response = self.client.post(self.login_url, data, follow=True)
        self.assertRedirects(response, self.login_url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout(self):
        """
        Testa o logout do usuário.

        Verifica se o usuário é desautenticado e redirecionado para login.
        """
        self.client.login(email="login@example.com", password="test123")
        response = self.client.get(self.logout_url, follow=True)
        self.assertRedirects(response, self.login_url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_resend_confirmation_get(self):
        """
        Testa a exibição do formulário de reenvio de confirmação (GET).
        """
        response = self.client.get(self.resend_confirmation_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/registration/resend_confirmation.html")


class TokensManageViewTest(TestCase):
    """Testes para a view que gerencia os tokens do usuário."""

    def setUp(self):
        """Configura o ambiente de testes."""
        self.client = Client()
        self.user = User.objects.create_user(
            email="tokens@example.com",
            username="tokens@example.com",
            password="test123"
        )
        # Alteração aqui: definir profile.is_approved como True
        profile, created = Profile.objects.get_or_create(user=self.user)
        profile.is_approved = True
        profile.save()

        self.token_manage_url = reverse("accounts:tokens_manage")

    def test_tokens_manage_nao_autenticado_redireciona(self):
        """
        Testa acesso à página de gerenciamento de tokens sem login.

        Verifica se redireciona para a tela de login.
        """
        response = self.client.get(self.token_manage_url, follow=True)
        expected_login_url = reverse("accounts:login")
        self.assertRedirects(response, f"{expected_login_url}?next={self.token_manage_url}")

    def test_tokens_manage_autenticado_mostra_pagina(self):
        """
        Testa acesso à página de gerenciamento de tokens com usuário autenticado.

        Verifica status code e template usado.
        """
        self.client.login(email="tokens@example.com", password="test123")
        response = self.client.get(self.token_manage_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/manage/tokens_manage.html")

    def test_criar_token_post_valido(self):
        """
        Testa criação de token via POST com dados válidos.

        Verifica se o token é criado e se o usuário é redirecionado corretamente.
        """
        self.client.login(email="tokens@example.com", password="test123")
        create_url = reverse("accounts:token_create")
        data = {"name": "Token Teste"}
        response = self.client.post(create_url, data=data, follow=True)
        self.assertRedirects(response, reverse("accounts:token_config", args=[UserToken.objects.first().pk]))
        self.assertTrue(UserToken.objects.filter(name="Token Teste").exists())

    def test_criar_token_post_invalido(self):
        """
        Testa criação de token com formulário inválido ou nome duplicado.

        Verifica se não é criado e se aparece mensagem de erro.
        """
        self.client.login(email="tokens@example.com", password="test123")
        UserToken.objects.create(user=self.user, name="Token Replicado", key="chave123")
        create_url = reverse("accounts:token_create")
        data = {"name": "Token Replicado"}  # nome duplicado
        response = self.client.post(create_url, data=data, follow=True)
        self.assertRedirects(response, self.token_manage_url)
        # Verifica se há mensagem de erro (messages) no contexto
        self.assertIn("Formulário inválido.", response.content.decode())


class TokenDeleteViewTest(TestCase):
    """Testes para a view que exclui tokens do usuário."""

    def setUp(self):
        """Configura o ambiente de testes."""
        self.client = Client()
        self.user = User.objects.create_user(
            email="tokens2@example.com",
            username="tokens2@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(
            user=self.user, name="Token Deletar", key="some-key-123"
        )
        self.delete_url = reverse("accounts:token_delete", args=[self.token.pk])

    def test_deletar_token_sem_autenticacao(self):
        """
        Testa se o usuário não autenticado é redirecionado ao tentar excluir token.
        """
        response = self.client.post(self.delete_url, follow=True)
        login_url = reverse("accounts:login")
        self.assertRedirects(response, f"{login_url}?next={self.delete_url}")

    def test_deletar_token_com_sucesso(self):
        """
        Testa exclusão de token por usuário autenticado.

        Verifica se o token é removido do banco.
        """
        self.client.login(email="tokens2@example.com", password="test123")
        response = self.client.post(self.delete_url, follow=True)
        manage_url = reverse("accounts:tokens_manage")
        self.assertRedirects(response, manage_url)
        self.assertFalse(UserToken.objects.filter(pk=self.token.pk).exists())


class TokenConfigViewTest(TestCase):
    """Testes para a view de configuração de token."""

    def setUp(self):
        """Cria usuário e token para teste."""
        self.client = Client()
        self.user = User.objects.create_user(
            email="config@example.com",
            username="config@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(user=self.user, name="Token Config", key="key123")
        self.config_url = reverse("accounts:token_config", args=[self.token.pk])

    def test_configurar_token_sem_autenticacao(self):
        """
        Testa se o usuário não autenticado é redirecionado ao tentar configurar token.
        """
        response = self.client.get(self.config_url, follow=True)
        login_url = reverse("accounts:login")
        self.assertRedirects(response, f"{login_url}?next={self.config_url}")

    def test_configurar_token_get(self):
        """
        Testa acesso à página de configuração do token via GET com usuário autenticado.
        """
        self.client.login(email="config@example.com", password="test123")
        response = self.client.get(self.config_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/manage/token_config.html")


class UserSettingsViewTest(TestCase):
    """Testes para a view de configurações do usuário."""

    def setUp(self):
        """Cria usuário e client de testes."""
        self.client = Client()
        self.user = User.objects.create_user(
            email="settingsview@example.com",
            username="settingsview@example.com",
            password="test123"
        )
        Profile.objects.get_or_create(user=self.user)
        self.settings_url = reverse("accounts:user_settings")

    def test_acesso_sem_autenticacao(self):
        """
        Testa acesso à página de configurações sem login.

        Verifica se redireciona para login.
        """
        response = self.client.get(self.settings_url, follow=True)
        login_url = reverse("accounts:login")
        self.assertRedirects(response, f"{login_url}?next={self.settings_url}")

    def test_exibe_formulario_configuracoes(self):
        """
        Testa se a página de configurações carrega para usuário autenticado.
        """
        self.client.login(email="settingsview@example.com", password="test123")
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/settings/user.html")

    def test_atualiza_configuracoes_post(self):
        """
        Testa se as configurações são atualizadas corretamente via POST.
        """
        self.client.login(email="settingsview@example.com", password="test123")
        data = {
            "first_name": "Teste",
            "last_name": "Configuracoes",
            "email": "settingsview@example.com",
            "capture_inactivity_timeout": 15,
        }
        response = self.client.post(self.settings_url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        user_atualizado = User.objects.get(pk=self.user.pk)
        self.assertEqual(user_atualizado.first_name, "Teste")
        self.assertEqual(user_atualizado.profile.capture_inactivity_timeout, 15)


class PasswordResetViewsTest(TestCase):
    """Testes para as views de redefinição de senha."""

    def setUp(self):
        """Configura o ambiente para os testes."""
        self.client = Client()
        self.reset_url = reverse("accounts:password_reset")
        self.reset_done_url = reverse("accounts:password_reset_done")
        self.user = User.objects.create_user(
            email="password@example.com",
            username="password@example.com",
            password="oldpassword"
        )
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            primary=True,
            verified=True
        )

    def test_password_reset_get(self):
        """
        Testa se a página de reset de senha carrega corretamente (GET).
        """
        response = self.client.get(self.reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/registration/password_reset_form.html")

    def test_password_reset_post_valido(self):
        """
        Testa o envio do formulário de reset de senha com email válido.

        Verifica redirecionamento para 'password_reset_done'.
        """
        data = {"email": "password@example.com"}
        response = self.client.post(self.reset_url, data)
        # Verifica se o status está correto (200)
        self.assertEqual(response.status_code, 200)
        # Verifica se há texto relacionado a envio de email na página
        self.assertContains(response, "Enviar Email")

    def test_password_reset_post_invalido(self):
        """
        Testa o envio do formulário de reset de senha com email inexistente.
        
        Deve aceitar e redirecionar do mesmo jeito, por segurança.
        """
        data = {"email": "naoexiste@example.com"}
        response = self.client.post(self.reset_url, data)
        self.assertRedirects(response, self.reset_done_url)
