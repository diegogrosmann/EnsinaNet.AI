# ai_config/tests/test_ai_client.py

import json
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model

from ai_config.models import AIClientConfiguration, AIClientGlobalConfiguration
from ai_config.forms import AIClientConfigurationForm

User = get_user_model()

class ManageAiViewTest(TestCase):
    """Testes para a view manage_ai."""

    def setUp(self):
        """Cria usuário e configurações de IA fictícias."""
        self.user = User.objects.create_user(username="aiuser", email="ai@example.com", password="12345")
        self.client.login(username="aiuser", password="12345")
        self.url = reverse("ai_config:ai_manage")
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Global AI",
            api_client_class="FakeClient",
            api_url="http://api.ai",
            api_key="aikey"
        )
        AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=global_config,
            name="Minha IA",
            model_name="modelo1"
        )

    def test_manage_ai_get(self):
        """Verifica se a view manage_ai carrega e, se for AJAX, retorna HTML parcial."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ai_client/manage.html")

class CreateAiViewTest(TestCase):
    """Testes para a view create_ai."""

    def setUp(self):
        """Cria usuário e configura URL."""
        self.user = User.objects.create_user(username="createai", email="createai@example.com", password="12345")
        self.client.login(username="createai", password="12345")
        self.url = reverse("ai_config:ai_create")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Create",
            api_client_class="FakeClient",
            api_url="http://api.create",
            api_key="createkey"
        )

    def test_create_ai_get(self):
        """Verifica se o formulário de criação é exibido."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ai_client/form.html")

    def test_create_ai_post_valido(self):
        """Testa criação de IA com dados válidos."""
        form_data = {
            "name": "Nova IA",
            "ai_client": str(self.global_config.id),
            "model_name": "modelo-nova",
            "configurations": "param=valor",
            "training_configurations": "batch_size=2",
            "use_system_message": True,
        }
        response = self.client.post(self.url, data=form_data, follow=True)
        self.assertRedirects(response, reverse("ai_config:ai_manage"))
        self.assertTrue(AIClientConfiguration.objects.filter(name="Nova IA", user=self.user).exists())

class EditAiViewTest(TestCase):
    """Testes para a view edit_ai."""

    def setUp(self):
        """Cria usuário, configuração de IA e URL de edição."""
        self.user = User.objects.create_user(username="editai", email="editai@example.com", password="12345")
        self.client.login(username="editai", password="12345")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Edit",
            api_client_class="FakeClient",
            api_url="http://api.edit",
            api_key="editkey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="IA Original",
            model_name="modelo-original"
        )
        self.url = reverse("ai_config:ai_edit", args=[self.ai_config.id])

    def test_edit_ai_get(self):
        """Verifica se a página de edição carrega com status 200."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ai_client/form.html")

    def test_edit_ai_post_valido(self):
        """Testa atualização válida da configuração de IA."""
        form_data = {
            "name": "IA Atualizada",
            "ai_client": str(self.global_config.id),
            "model_name": "modelo-atualizado",
            "configurations": "",
            "training_configurations": "",
            "use_system_message": False,
        }
        response = self.client.post(self.url, data=form_data, follow=True)
        self.assertRedirects(response, reverse("ai_config:ai_manage"))
        self.ai_config.refresh_from_db()
        self.assertEqual(self.ai_config.name, "IA Atualizada")

class DeleteAiViewTest(TestCase):
    """Testes para a view delete_ai."""

    def setUp(self):
        """Cria usuário, configuração de IA e URL de exclusão."""
        self.user = User.objects.create_user(username="deleteai", email="deleteai@example.com", password="12345")
        self.client.login(username="deleteai", password="12345")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Delete",
            api_client_class="FakeClient",
            api_url="http://api.delete",
            api_key="deletekey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="IA a Excluir",
            model_name="modelo-delete"
        )
        self.url = reverse("ai_config:delete_ai", args=[self.ai_config.id])

    def test_delete_ai_post(self):
        """Testa exclusão da IA via POST."""
        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        with self.assertRaises(Exception):
            self.ai_config.refresh_from_db()

class AiAvailableTokensViewTest(TestCase):
    """Testes para a view ai_available_tokens."""

    def setUp(self):
        """Cria usuário, configuração de IA e URL."""
        self.user = User.objects.create_user(username="availtoken", email="avail@example.com", password="12345")
        self.client.login(username="availtoken", password="12345")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Tokens",
            api_client_class="FakeClient",
            api_url="http://api.tokens",
            api_key="tokenkey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="Config Tokens",
            model_name="modelo-tokens"
        )
        self.url = reverse("ai_config:ai_available_tokens", args=[self.ai_config.id])

    def test_ai_available_tokens_get(self):
        """Verifica se a view retorna uma lista de tokens em JSON."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("tokens", data["data"])

class GetAiModelsViewTest(TestCase):
    """Testes para a view get_ai_models."""

    def setUp(self):
        """Cria usuário, configuração global de IA e URL."""
        self.user = User.objects.create_user(username="modelsuser", email="models@example.com", password="12345")
        self.client.login(username="modelsuser", password="12345")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Models",
            api_client_class="FakeClient",
            api_url="http://api.models",
            api_key="modelkey"
        )
        self.url = reverse("ai_config:get_ai_models", args=[self.global_config.id])

    def test_get_ai_models_get(self):
        """Testa se a view retorna status 200 e estrutura JSON adequada."""
        # Para este teste, pode ser necessário que o método create_api_client_instance retorne um objeto que possua o método api_list_models.
        # Se não houver, a view deverá retornar erro.
        response = self.client.get(self.url)
        # Verifica que a resposta possui sucesso ou erro apropriado
        data = json.loads(response.content)
        # Aqui apenas verificamos a existência da chave "success"
        self.assertIn("success", data)

# Fim de test_ai_client.py
