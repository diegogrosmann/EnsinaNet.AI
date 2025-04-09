# ai_config/tests/test_token.py

import json
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import UserToken
from ai_config.models import TokenAIConfiguration, AIClientConfiguration, AIClientGlobalConfiguration, AIClientTokenConfig
from core1.types import APPResponse

User = get_user_model()

class PromptConfigViewTest(TestCase):
    """Testes para a view prompt_config."""

    def setUp(self):
        """Cria usuário, token e configuração de IA para teste."""
        self.user = User.objects.create_user(username="tokenuser", email="token@example.com", password="12345")
        self.client.login(username="tokenuser", password="12345")
        self.token = UserToken.objects.create(user=self.user, name="MeuToken", key="123abc")
        self.url = reverse("ai_config:prompt_config", args=[self.token.id])

    def test_prompt_config_get(self):
        """Verifica se a view GET retorna status 200 e utiliza o template correto."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "token/prompt_config.html")

    def test_prompt_config_post_sem_prompt(self):
        """Testa POST com dados inválidos (prompt vazio)."""
        post_data = {"base_instruction": "Instrução", "prompt": "", "responses": "Resposta"}
        response = self.client.post(self.url, data=post_data)
        # Se for AJAX, deve retornar JSON com erro; senão, redirecionar
        if response["Content-Type"].startswith("application/json"):
            data = json.loads(response.content)
            self.assertFalse(data["success"])
            self.assertIn("obrigatório", data["error"])
        else:
            self.assertRedirects(response, reverse("accounts:token_config", args=[self.token.id]))

class TokenAiLinkViewTest(TestCase):
    """Testes para a view token_ai_link."""

    def setUp(self):
        """Cria usuário, token e algumas configurações de IA fictícias."""
        self.user = User.objects.create_user(username="linkuser", email="link@example.com", password="12345")
        self.client.login(username="linkuser", password="12345")
        self.token = UserToken.objects.create(user=self.user, name="TokenLink", key="key123")
        # Cria uma configuração de IA para o usuário
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global IA",
            api_client_class="FakeClient",
            api_url="http://api.fake",
            api_key="fakekey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="Config IA",
            model_name="modelo1"
        )
        self.url = reverse("ai_config:token_ai_link", args=[self.token.id])

    def test_token_ai_link_get(self):
        """Verifica se a view retorna o template esperado."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "token/ai_link.html")

class TokenAiToggleViewTest(TestCase):
    """Testes para a view token_ai_toggle."""

    def setUp(self):
        """Cria usuário, token e configuração de IA para testar toggle em massa."""
        self.user = User.objects.create_user(username="toggleuser", email="toggle@example.com", password="12345")
        self.client.login(username="toggleuser", password="12345")
        self.token = UserToken.objects.create(user=self.user, name="TokenToggle", key="keytoggle")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Toggle",
            api_client_class="FakeClient",
            api_url="http://api.toggle",
            api_key="togglekey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="Config Toggle",
            model_name="modelo-toggle"
        )
        self.url = reverse("ai_config:token_ai_toggle")

    def test_token_ai_toggle_post_valido(self):
        """Testa POST com payload JSON válido para alternar configurações."""
        payload = {
            str(self.token.id): {
                str(self.ai_config.id): True
            }
        }
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        # Verifica se a configuração foi criada/atualizada
        from ai_config.models import AIClientTokenConfig
        self.assertTrue(AIClientTokenConfig.objects.filter(token=self.token, ai_config=self.ai_config, enabled=True).exists())

    def test_token_ai_toggle_post_payload_invalido(self):
        """Testa POST com payload JSON malformado."""
        response = self.client.post(
            self.url,
            data="not a json",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["success"])

# Fim de test_token.py
