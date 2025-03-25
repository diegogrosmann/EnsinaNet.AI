# accounts/tests/test_backends.py

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from accounts.backends import EmailBackend

User = get_user_model()

class EmailBackendTest(TestCase):
    """Testes para o backend de autenticação por email (EmailBackend)."""

    def setUp(self):
        """Configura o ambiente antes de cada teste."""
        self.factory = RequestFactory()
        self.backend = EmailBackend()
        self.email = "test@example.com"
        self.password = "strong_password"

        # Cria um usuário para testes
        self.user = User.objects.create(
            username=self.email,
            email=self.email,
            password=make_password(self.password),
            is_active=True
        )

    def test_autenticar_com_credenciais_validas(self):
        """
        Testa se o backend autentica corretamente com credenciais válidas.

        Verifica se, ao passar um email e senha corretos, 
        o backend retorna o objeto de usuário apropriado.
        """
        request = self.factory.post("/fake-url/")
        user = self.backend.authenticate(
            request=request,
            username=self.email,
            password=self.password
        )
        self.assertIsNotNone(user)
        self.assertEqual(user.email, self.user.email)

    def test_autenticar_com_senha_incorreta(self):
        """
        Testa autenticação falha com senha incorreta.
        
        Verifica se o retorno é None quando a senha não confere.
        """
        request = self.factory.post("/fake-url/")
        user = self.backend.authenticate(
            request=request,
            username=self.email,
            password="wrong_password"
        )
        self.assertIsNone(user)

    def test_autenticar_com_email_inexistente(self):
        """
        Testa autenticação falha com email que não existe.
        
        Verifica se o retorno é None quando o email não está cadastrado.
        """
        request = self.factory.post("/fake-url/")
        user = self.backend.authenticate(
            request=request,
            username="inexistente@example.com",
            password="somepassword"
        )
        self.assertIsNone(user)

    def test_autenticar_sem_credenciais_completas(self):
        """
        Testa autenticação sem fornecer email ou senha.
        
        Verifica se o retorno é None quando não há dados suficientes.
        """
        request = self.factory.post("/fake-url/")
        user = self.backend.authenticate(request=request)
        self.assertIsNone(user)
