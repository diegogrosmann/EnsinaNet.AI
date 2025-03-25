# ai_config/tests/test_tasks.py

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from ai_config.tasks import update_training_status
from ai_config.models import AITraining, AIClientConfiguration, AIClientGlobalConfiguration, User
from accounts.models import UserToken
from core.types.training import AITrainingStatus
from core.exceptions import AIConfigError, TrainingError

class UpdateTrainingStatusTaskTest(TestCase):
    """Testes para a task update_training_status, responsável por atualizar status de treinamentos."""

    def setUp(self):
        """Prepara dados para os testes."""
        self.user = User.objects.create_user(username="teste_user", email="teste@example.com", password="12345678")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Test Global Config",
            api_client_class="FakeClient",
            api_url="http://fakeapi.com",
            api_key="fake-key"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user_id=1,  # Pode criar um usuário real se necessário
            ai_client=self.global_config,
            name="My AI Config",
            model_name="test-model"
        )
        self.job_id_ok = str(uuid.uuid4())
        self.job_id_fail = str(uuid.uuid4())

        # Cria um treinamento em progresso
        self.training_ok = AITraining.objects.create(
            ai_config=self.ai_config,
            job_id=self.job_id_ok,
            status="in_progress"
        )
        # Cria outro treinamento em progresso
        self.training_fail = AITraining.objects.create(
            ai_config=self.ai_config,
            job_id=self.job_id_fail,
            status="in_progress"
        )

    @patch("ai_config.models.AIClientGlobalConfiguration.create_api_client_instance")
    def test_update_training_status_ai_config_error(self, mock_client):
        """
        Testa se a task marca erro adequadamente quando há problema de configuração (AIConfigError).
        """
        fake_client_instance = MagicMock()
        mock_client.return_value = fake_client_instance
        fake_client_instance.get_training_status.side_effect = AIConfigError("Config inválida")

        result = update_training_status()
        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["failure_count"], 1)

        self.training_ok.refresh_from_db()
        self.assertIn("Config inválida", self.training_ok.error)

    @patch("ai_config.models.AIClientGlobalConfiguration.create_api_client_instance")
    def test_update_training_status_excecao_inesperada(self, mock_client):
        """
        Testa se a task lida com exceções genéricas, marcando o erro no campo 'error'.
        """
        fake_client_instance = MagicMock()
        mock_client.return_value = fake_client_instance
        fake_client_instance.get_training_status.side_effect = ValueError("Erro inesperado")

        result = update_training_status()
        self.assertEqual(result["failure_count"], 1)

        self.training_ok.refresh_from_db()
        self.assertIn("Erro interno: Erro inesperado", self.training_ok.error)

    @patch("ai_config.models.AIClientGlobalConfiguration.create_api_client_instance")
    def test_update_training_status_sem_treinamentos(self, mock_client):
        """
        Testa a task quando não há treinamentos in_progress (não deve falhar).
        """
        AITraining.objects.all().delete()
        result = update_training_status()
        self.assertEqual(result["success_count"], 0)
        self.assertEqual(result["failure_count"], 0)
        self.assertEqual(result["total"], 0)
        mock_client.assert_not_called()
