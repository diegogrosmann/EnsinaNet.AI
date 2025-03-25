# accounts/tests/test_admin.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from accounts.models import Profile, UserToken
from django.contrib.admin.sites import AdminSite
from accounts.admin import ProfileAdmin, UserTokenAdmin

User = get_user_model()

class AdminProfileTest(TestCase):
    """Testes para a interface admin de Profile."""
    
    def setUp(self):
        """Cria usuário admin e outro usuário normal para teste."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            username="admin@example.com",
            password="adminpass"
        )
        self.client.login(email="admin@example.com", password="adminpass")
        self.user = User.objects.create_user(
            email="normal@example.com",
            username="normal@example.com",
            password="test123"
        )
        self.profile = Profile.objects.get(user=self.user)

    def test_profile_list_no_admin(self):
        """
        Testa se a listagem de Profile no admin carrega corretamente.
        """
        url = reverse("admin:accounts_profile_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.profile.user.email)

    def test_profile_change_view(self):
        """
        Testa página de edição de Profile no admin.
        """
        url = reverse("admin:accounts_profile_change", args=[self.profile.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.profile.user.email)


class AdminUserTokenTest(TestCase):
    """Testes para a interface admin de UserToken."""

    def setUp(self):
        """Cria usuário admin e um usuário normal com token."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            username="admin@example.com",
            password="adminpass"
        )
        self.client.login(email="admin@example.com", password="adminpass")
        self.user = User.objects.create_user(
            email="tokenuser@example.com",
            username="tokenuser@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(user=self.user, name="Admin Token", key="somekey12345")

    def test_usertoken_list_no_admin(self):
        """
        Testa se a listagem de UserToken no admin carrega corretamente.
        """
        url = reverse("admin:accounts_usertoken_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.token.name)

    def test_usertoken_change_view(self):
        """
        Testa página de edição de UserToken no admin.
        """
        url = reverse("admin:accounts_usertoken_change", args=[self.token.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.token.name)
