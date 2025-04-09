# ai_config/tests/test_models.py

import os
import uuid
import json
from django.test import TestCase, override_settings
from django.conf import settings
from ai_config.models import (
    AITrainingFile,
    TrainingCapture,
    AIClientGlobalConfiguration,
    AIClientConfiguration,
    TokenAIConfiguration,
    AITraining,
)
from accounts.models import UserToken, Profile, User
from core1.types.training import AITrainingExample, AITrainingExampleCollection

@override_settings(MEDIA_ROOT=os.path.join(settings.BASE_DIR, "test_media"))
class AITrainingFileTest(TestCase):
    """Testes para o modelo AITrainingFile."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="test123"
        )
        self.file_model = AITrainingFile.objects.create(
            user=self.user,
            name="Meu Arquivo de Teste"
        )
        # Garantir que o diretório de mídia de teste exista
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'training_files'), exist_ok=True)

    def test_file_data_setter_e_getter(self):
        """
        Testa se é possível definir e obter dados de treinamento (file_data).
        """
        # Cria um exemplo de treinamento válido
        example = AITrainingExample(system_message="Instrução do sistema", user_message="Olá", response="Hello")
        collection = AITrainingExampleCollection()
        collection.examples.append(example)
        
        # Define os dados e salva
        self.file_model.file_data = collection
        self.file_model.save()
        
        # Verifica se o arquivo foi salvo corretamente
        self.assertEqual(len(self.file_model.file_data.examples), 1)
        self.assertTrue(os.path.exists(self.file_model.get_full_path()))

    def test_nao_salvar_se_nao_houver_exemplos(self):
        """
        Testa que não é possível salvar o arquivo se não houver exemplos.
        """
        # Criar uma coleção vazia diretamente (sem usar o create que lançaria exceção)
        empty_collection = AITrainingExampleCollection()
        self.file_model.file_data = empty_collection
        
        # Deve falhar ao tentar salvar uma coleção vazia
        with self.assertRaises(Exception):
            self.file_model.save()

@override_settings(MEDIA_ROOT=os.path.join(settings.BASE_DIR, "test_media"))
class TrainingCaptureTest(TestCase):
    """Testes para o modelo TrainingCapture (capturas temporárias de treinamento)."""

    def setUp(self):
        """Cria usertoken e config para testes."""
        self.user = User.objects.create_user(
            username="captureuser",
            email="capture@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(
            user=self.user,
            name="CaptureToken",
            key="capture-key"
        )
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Global Config X",
            api_client_class="FakeClient",
            api_url="http://api.com",
            api_key="abcdef"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="Capture AI",
            model_name="model-capture"
        )
        self.capture = TrainingCapture.objects.create(
            token=self.token,
            ai_client_config=self.ai_config,
            is_active=True
        )

    def test_file_data_manipulacao(self):
        """Testa se é possível manipular file_data na captura."""
        self.assertTrue(self.capture.is_active)
        self.assertEqual(len(self.capture.file_data.examples), 0)

        collection = self.capture.file_data
        # Crie um novo exemplo e adicione-o à lista
        novo_exemplo = AITrainingExample(
            system_message="", 
            user_message="Pergunta", 
            response="Resposta"
        )
        collection.examples.append(novo_exemplo)
        # Atualize a propriedade file_data (caso o setter reaja à nova lista)
        self.capture.file_data = collection
        self.capture.save()

        self.assertTrue(os.path.exists(self.capture.get_full_path()), "Arquivo temporário deve existir")
        self.assertEqual(len(self.capture.file_data.examples), 1)

class TokenAIConfigurationTest(TestCase):
    """Testes para o modelo TokenAIConfiguration."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="tokenuser",
            email="tokenuser@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(user=self.user, name="Token 1", key="xxxyyy")
        self.config = TokenAIConfiguration.objects.create(
            token=self.token,
            base_instruction="Base Instruction",
            prompt="Hello, World!",
            responses="Ok"
        )

    def test_to_prompt_config(self):
        """Testa se to_prompt_config retorna AIPromptConfig válido."""
        prompt_config = self.config.to_prompt_config()
        self.assertEqual(prompt_config.system_message, "Base Instruction")
        self.assertEqual(prompt_config.user_message, "Hello, World!")
        self.assertEqual(prompt_config.response, "Ok")

class AITrainingTest(TestCase):
    """Testes para o modelo AITraining."""
    # Poderíamos complementar aqui testes de cancelamento, get_training_data, etc.
    pass
