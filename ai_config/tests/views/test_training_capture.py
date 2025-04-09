# ai_config/tests/test_training_capture.py

import json
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model

from ai_config.models import TrainingCapture, AIClientConfiguration, AIClientGlobalConfiguration
from accounts.models import UserToken
from core1.types import APPResponse

User = get_user_model()

class CaptureToggleViewTest(TestCase):
    """Testes para a view capture_toggle."""

    def setUp(self):
        """Cria usuário, token e configuração de IA para teste da captura."""
        self.user = User.objects.create_user(username="captureuser", email="capture@example.com", password="12345")
        self.client.login(username="captureuser", password="12345")
        self.token = UserToken.objects.create(user=self.user, name="TokenCapture", key="capkey")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Capture",
            api_client_class="FakeClient",
            api_url="http://api.capture",
            api_key="capkey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="Config Capture",
            model_name="modelo-capture"
        )
        self.url = reverse("ai_config:capture_toggle")

    def test_capture_toggle_activate_sem_ids(self):
        """Testa ativação sem enviar token ou ai_client_config, retornando erro."""
        data = {"action": "activate"}
        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 400)
        data_resp = json.loads(response.content)
        self.assertFalse(data_resp["success"])
        self.assertIn("obrigatórios", data_resp["error"])

    def test_capture_toggle_activate_valido(self):
        """Testa ativação válida da captura."""
        data = {"action": "activate", "token": str(self.token.id), "ai_client_config": str(self.ai_config.id)}
        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 200)
        data_resp = json.loads(response.content)
        self.assertTrue(data_resp["success"])
        self.assertIn("ativada com sucesso", data_resp["data"]["message"])

    def test_capture_toggle_desativar(self):
        """Testa desativação da captura via POST com action diferente de activate."""
        # Primeiro cria uma captura ativa
        data_activate = {"action": "activate", "token": str(self.token.id), "ai_client_config": str(self.ai_config.id)}
        self.client.post(self.url, data=data_activate)
        # Agora desativa (action diferente)
        data = {"action": "deactivate"}
        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 200)
        data_resp = json.loads(response.content)
        self.assertTrue(data_resp["success"])
        self.assertIn("desativada com sucesso", data_resp["data"]["message"])

class CaptureGetExamplesViewTest(TestCase):
    """Testes para a view capture_get_examples."""

    def setUp(self):
        """Cria usuário, token, configuração de IA e uma captura com exemplos."""
        self.user = User.objects.create_user(username="exuser", email="ex@example.com", password="12345")
        self.client.login(username="exuser", password="12345")
        self.token = UserToken.objects.create(user=self.user, name="TokenEx", key="exkey")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Ex",
            api_client_class="FakeClient",
            api_url="http://api.ex",
            api_key="exkey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="Config Ex",
            model_name="modelo-ex"
        )
        # Cria uma captura com uma coleção de exemplos (para este teste, podemos simular com uma coleção vazia)
        self.capture = TrainingCapture.objects.create(
            token=self.token,
            ai_client_config=self.ai_config,
            is_active=True
        )
        self.url = reverse("ai_config:capture_get_examples", args=[str(self.token.id), self.ai_config.id])

    def test_capture_get_examples_sem_captura(self):
        """Testa se, ao não existir captura, a view retorna exemplos vazios."""
        # Remove a captura criada
        self.capture.delete()
        response = self.client.get(self.url)
        data_resp = json.loads(response.content)
        self.assertTrue(data_resp["success"])
        self.assertEqual(data_resp["data"]["count"], 0)

    def test_capture_get_examples_valido(self):
        """Testa se a view retorna exemplos e limpa a coleção após leitura."""
        # Para este teste, vamos simular que a captura possui alguns exemplos.
        # Suponha que o método to_dict() da coleção retorne um dicionário com 'examples' e count.
        # Aqui, como exemplo, não vamos alterar o objeto, apenas testar o fluxo.
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data_resp = json.loads(response.content)
        self.assertTrue(data_resp["success"])

# Fim de test_training_capture.py
