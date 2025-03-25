# ai_config/tests/test_training.py

import json
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model

from ai_config.models import AITraining, AITrainingFile, AIClientConfiguration, AIClientGlobalConfiguration
from core.types import APPResponse, AITrainingStatus

User = get_user_model()

class TrainingCenterViewTest(TestCase):
    """Testes para a view training_center."""

    def setUp(self):
        """Cria usuário e alguns objetos para exibição no Training Center."""
        self.user = User.objects.create_user(username="centeruser", email="center@example.com", password="12345")
        self.client.login(username="centeruser", password="12345")
        self.url = reverse("ai_config:training_center")
        # Cria um arquivo de treinamento fictício
        AITrainingFile.objects.create(user=self.user, name="arquivo_center", file_data=b'{"examples": []}')
        # Cria uma configuração de IA fictícia
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Center",
            api_client_class="FakeClient",
            api_url="http://api.center",
            api_key="centerkey"
        )
        AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=global_config,
            name="Config Center",
            model_name="modelo-center"
        )

    def test_training_center_get(self):
        """Verifica se a página do Training Center carrega corretamente."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "training/center.html")

class TrainingAiViewTest(TestCase):
    """Testes para a view training_ai."""

    def setUp(self):
        """Cria usuário, arquivo e configuração de IA para iniciar treinamento."""
        self.user = User.objects.create_user(username="trainuser", email="train@example.com", password="12345")
        self.client.login(username="trainuser", password="12345")
        self.url = reverse("ai_config:training_ai")
        # Cria um arquivo de treinamento fictício
        self.training_file = AITrainingFile.objects.create(user=self.user, name="arquivo_train", file_data=b'{"examples": []}')
        # Cria uma configuração de IA fictícia (supondo que client.can_train seja True)
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Train",
            api_client_class="FakeClient",
            api_url="http://api.train",
            api_key="trainkey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=global_config,
            name="Config Train",
            model_name="modelo-train"
        )
        # Para simplificar, não mockamos o método de treinamento; vamos apenas testar o fluxo de validação
        self.post_data = {
            "selected_ais": [str(self.ai_config.id)],
            "file_id": str(self.training_file.id)
        }

    def test_training_ai_get_metodo_nao_permitido(self):
        """Verifica se método GET retorna erro (405)."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_training_ai_post_sem_ais(self):
        """Testa POST sem seleção de IAs retorna erro."""
        data = {"selected_ais": [], "file_id": str(self.training_file.id)}
        response = self.client.post(self.url, data=data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        data_resp = json.loads(response.content)
        self.assertFalse(data_resp["success"])

    # Outros testes para training_ai podem envolver mockar o método client.train para simular respostas

class TrainingMonitorViewTest(TestCase):
    """Testes para a view training_monitor."""

    def setUp(self):
        """Cria usuário e alguns treinamentos fictícios."""
        self.user = User.objects.create_user(username="monitoruser", email="monitor@example.com", password="12345")
        self.client.login(username="monitoruser", password="12345")
        self.url = reverse("ai_config:training_monitor")
        # Cria um treinamento fictício
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Monitor",
            api_client_class="FakeClient",
            api_url="http://api.monitor",
            api_key="monitorkey"
        )
        ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=global_config,
            name="Config Monitor",
            model_name="modelo-monitor"
        )
        AITraining.objects.create(
            ai_config=ai_config,
            job_id="job123",
            status="in_progress",
            progress=0.5
        )

    def test_training_monitor_sem_parametros(self):
        """Verifica se a view retorna status geral de treinamentos quando não há parâmetros."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIn("trainings", data["data"])

class TrainingCancelViewTest(TestCase):
    """Testes para a view training_cancel."""

    def setUp(self):
        """Cria usuário e um treinamento fictício para cancelamento."""
        self.user = User.objects.create_user(username="canceluser", email="cancel@example.com", password="12345")
        self.client.login(username="canceluser", password="12345")
        # Cria configuração e treinamento
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Cancel",
            api_client_class="FakeClient",
            api_url="http://api.cancel",
            api_key="cancelkey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=global_config,
            name="Config Cancel",
            model_name="modelo-cancel"
        )
        self.training = AITraining.objects.create(
            ai_config=self.ai_config,
            job_id="job_cancel",
            status="in_progress",
            progress=0.2
        )
        self.url = reverse("ai_config:training_cancel", args=[self.training.id])

    def test_training_cancel_get_nao_permitido(self):
        """Verifica se método GET não é permitido."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_training_cancel_post(self):
        """Testa cancelamento via POST.
        
        Para este teste, pode-se simular que o método cancel_training retorna True.
        """
        # Força cancelamento simulando sucesso com monkey-patching
        self.training.cancel_training = lambda: True
        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

class TrainingDeleteViewTest(TestCase):
    """Testes para a view training_delete."""

    def setUp(self):
        """Cria usuário e um treinamento para exclusão."""
        self.user = User.objects.create_user(username="deleteTrain", email="deleteTrain@example.com", password="12345")
        self.client.login(username="deleteTrain", password="12345")
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Delete",
            api_client_class="FakeClient",
            api_url="http://api.delete",
            api_key="deletekey"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=global_config,
            name="Config Delete",
            model_name="modelo-delete"
        )
        self.training = AITraining.objects.create(
            ai_config=self.ai_config,
            job_id="job_delete",
            status="completed",
            progress=1.0
        )
        self.url = reverse("ai_config:training_delete", args=[self.training.id])

    def test_training_delete_post(self):
        """Testa exclusão de treinamento via POST."""
        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        # Verifica se o treinamento foi excluído
        with self.assertRaises(Exception):
            self.training.refresh_from_db()

# Fim de test_training.py
