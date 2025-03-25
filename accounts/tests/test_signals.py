# accounts/tests/test_signals.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Profile

User = get_user_model()

class SignalsTest(TestCase):
    """Testes para os signals de criação de Profile e aprovação de usuário."""

    def test_criacao_de_profile_automatico(self):
        """
        Testa se ao criar um novo usuário, o Profile é criado automaticamente pelo signal.
        """
        user = User.objects.create_user(
            email="sinal@example.com",
            username="sinal@example.com",
            password="test123"
        )
        profile = Profile.objects.get(user=user)
        self.assertIsNotNone(profile)

    def test_aprovar_usuario_ativa_conta(self):
        """
        Testa se ao aprovar um profile, o usuário é ativado automaticamente.
        """
        user = User.objects.create_user(
            email="aprovar@example.com",
            username="aprovar@example.com",
            password="test123",
            is_active=False
        )
        profile = Profile.objects.get(user=user)
        profile.is_approved = True
        profile.save()

        user.refresh_from_db()
        self.assertTrue(user.is_active)
