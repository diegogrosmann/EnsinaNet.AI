# accounts/tests/test_authentication.py

from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework import exceptions
from django.contrib.auth import get_user_model
from accounts.authentication import CustomTokenAuthentication
from accounts.models import UserToken

User = get_user_model()

class CustomTokenAuthenticationTest(TestCase):
    """Testes para a CustomTokenAuthentication que usa o modelo UserToken."""

    def setUp(self):
        """Configura um usuário e token para teste."""
        self.user = User.objects.create_user(
            email="api@example.com",
            username="api@example.com",
            password="test123",
            is_active=True
        )
        self.token = UserToken.objects.create(user=self.user, name="API Token")
        self.auth = CustomTokenAuthentication()
        self.factory = APIRequestFactory()

    def test_autenticar_credenciais_validas(self):
        """
        Testa autenticação de credenciais válidas.

        Verifica se retorna tupla (usuário, token) para chave correta.
        """
        user, token_obj = self.auth.authenticate_credentials(self.token.key)
        self.assertEqual(user, self.user)
        self.assertEqual(token_obj, self.token)

    def test_token_invalido(self):
        """
        Testa erro de token inválido.

        Verifica se é levantada 'AuthenticationFailed' para chave desconhecida.
        """
        with self.assertRaises(exceptions.AuthenticationFailed):
            self.auth.authenticate_credentials("chave_inexistente")

    def test_usuario_inativo(self):
        """
        Testa autenticação com usuário inativo.

        Verifica se é levantada 'AuthenticationFailed'.
        """
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(exceptions.AuthenticationFailed):
            self.auth.authenticate_credentials(self.token.key)
