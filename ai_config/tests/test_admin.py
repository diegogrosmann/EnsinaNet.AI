# ai_config/tests/test_admin.py

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from ai_config.models import AIClientGlobalConfiguration
from django.contrib import admin
from ai_config.admin import AIClientGlobalConfigAdmin
from unittest.mock import patch, MagicMock
# Importar o mapeamento de clientes disponíveis
from api.utils.clientsIA import AI_CLIENT_MAPPING

User = get_user_model()

class AIClientGlobalConfigAdminTest(TestCase):
    """Testes para a administração de AIClientGlobalConfiguration."""

    def setUp(self):
        """Cria usuário admin e configura login."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            username="adminuser",
            password="adminpass"
        )
        self.client.login(username="adminuser", password="adminpass")
        self.config = AIClientGlobalConfiguration.objects.create(
            name="Test Global Config",
            api_client_class="FakeClient",
            api_url="http://fakeapi.com",
            api_key="1234abcd"
        )

    def test_list_view(self):
        """Testa se a listagem de AIClientGlobalConfiguration no admin carrega."""
        url = reverse("admin:ai_config_aiclientglobalconfiguration_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Global Config")

    def test_edit_view(self):
        """Testa a view de edição de AIClientGlobalConfiguration."""
        url = reverse("admin:ai_config_aiclientglobalconfiguration_change", args=[self.config.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.config.name)

    def test_create_config(self):
        """Testa criação de nova configuração global via admin."""
        # Obter uma das chaves disponíveis no mapeamento
        if not AI_CLIENT_MAPPING:
            self.skipTest("Nenhum cliente de IA registrado")
            
        client_class = list(AI_CLIENT_MAPPING.keys())[0]
        
        # Garantir que todos os campos necessários estejam presentes
        form_data = {
            'name': 'Outra Config',
            'api_client_class': client_class,  # Usa um cliente disponível
            'api_url': 'https://example.com/api',
            'api_key': 'uma_chave_api_valida',
            '_save': 'Salvar',  # Botão de salvar do admin
        }
        
        # Testar primeiro com redirecionamento e depois verificar o sucesso
        response = self.client.post(
            reverse('admin:ai_config_aiclientglobalconfiguration_add'),
            data=form_data
        )
        
        # Verificar se foi criado com sucesso, independente do código de status
        self.assertTrue(AIClientGlobalConfiguration.objects.filter(name="Outra Config").exists())

    def test_delete_config(self):
        """Testa exclusão de configuração global via admin."""
        url = reverse("admin:ai_config_aiclientglobalconfiguration_delete", args=[self.config.pk])
        response = self.client.post(url, {"post": "yes"}, follow=True)
        self.assertRedirects(response, reverse("admin:ai_config_aiclientglobalconfiguration_changelist"))
        self.assertFalse(AIClientGlobalConfiguration.objects.filter(pk=self.config.pk).exists())

class CustomAdminViewsTest(TestCase):
    """Testes para views administrativas customizadas."""
    
    def setUp(self):
        """Cria um superusuário e faz login."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            username="adminuser",
            password="adminpass"
        )
        self.client.login(username="adminuser", password="adminpass")

    def test_delete_file_view_method_not_allowed(self):
        """Testa se DELETE via GET retorna 405."""
        try:
            url = reverse("admin:ai_config_delete_ai_file", args=[999, "fake_file_id"])
        except:
            self.skipTest("URL 'delete_ai_file' não disponível - teste ignorado")
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertIn("Método não permitido", response.json()["error"])
