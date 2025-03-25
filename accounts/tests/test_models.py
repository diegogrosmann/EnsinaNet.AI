# accounts/tests/test_models.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Profile, UserToken

User = get_user_model()

class ProfileModelTest(TestCase):
    """Testes para o modelo Profile."""

    def setUp(self):
        """Cria um usuário e um Profile para testes."""
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="test123"
        )
        self.profile = Profile.objects.get(user=self.user)

    def test_criacao_automatica_do_profile(self):
        """
        Testa se o Profile é criado automaticamente para um novo usuário.

        Verifica se o objeto Profile realmente existe após a criação do usuário.
        """
        self.assertIsNotNone(self.profile)
        self.assertFalse(self.profile.is_approved)

    def test_str_do_profile(self):
        """
        Testa o método __str__ do modelo Profile.

        Verifica se a string de representação é como esperado.
        """
        self.assertEqual(str(self.profile), f"{self.user.email} Profile")

    def test_salvar_profile_log(self):
        """
        Testa se o Profile é salvo corretamente.

        Verifica se não ocorrem exceções ao salvar o profile e 
        se o 'capture_inactivity_timeout' está no valor padrão.
        """
        self.profile.capture_inactivity_timeout = 15
        self.profile.save()
        self.assertEqual(Profile.objects.get(pk=self.profile.pk).capture_inactivity_timeout, 15)


class UserTokenModelTest(TestCase):
    """Testes para o modelo UserToken."""

    def setUp(self):
        """Cria um usuário para teste e um token."""
        self.user = User.objects.create_user(
            username="tokenuser@example.com",
            email="tokenuser@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(
            user=self.user,
            name="Token de Teste",
            key="",
        )

    def test_token_criado_com_chave_unica(self):
        """
        Testa se a chave do token é gerada automaticamente.

        Verifica se o campo 'key' foi preenchido com uma chave única 
        após a criação.
        """
        self.assertNotEqual(self.token.key, "")
        self.assertEqual(len(self.token.key), 32)  # pois estamos usando uuid4().hex (32 chars)

    def test_str_do_token(self):
        """
        Testa o método __str__ do modelo UserToken.

        Verifica a formatação com nome do token e prefixo da chave.
        """
        token_str = str(self.token)
        self.assertIn(self.token.name, token_str)
        self.assertIn(self.token.key[:8], token_str)

    def test_unique_together_user_name(self):
        """
        Testa a restrição de unicidade (user, name).

        Verifica se tentar criar outro token com mesmo user e name gera erro.
        """
        with self.assertRaises(Exception):
            UserToken.objects.create(
                user=self.user,
                name="Token de Teste"  # mesmo nome
            )
