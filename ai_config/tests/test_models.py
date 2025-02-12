from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import UserToken
from ai_config.models import AIClientGlobalConfiguration, AITrainingFile, TokenAIConfiguration

class AIClientGlobalConfigModelTest(TestCase):
    def test_str(self):
        conf = AIClientGlobalConfiguration.objects.create(
            name="OpenAI",
            api_client_class="OpenAi",
            api_url="https://api.openai.com/v1",
            api_key="12345"
        )
        self.assertIn("(OpenAi) OpenAI", str(conf))


class AITrainingFileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", "testuser@example.com", "pass")

    def test_training_file_creation(self):
        file = AITrainingFile.objects.create(
            user=self.user,
            name="treino1",
            file="dummy/path/to/file.txt"
        )
        self.assertIsNotNone(file.uploaded_at)
        self.assertEqual(str(file), f"Arquivo de Treinamento de {self.user.email} carregado em {file.uploaded_at}")


class TokenAIConfigurationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user2", "u2@example.com", "pass2")
        self.token = UserToken.objects.create(user=self.user, name="token2")

    def test_str(self):
        config = TokenAIConfiguration.objects.create(token=self.token, base_instruction="Base", prompt="Prompt")
        self.assertIn(self.token.name, str(config))
