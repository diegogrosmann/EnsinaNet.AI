# ai_config/tests/test_clientsIA.py

import io
import html
import json
from typing import Any
import uuid
import time
from datetime import datetime

from django.test import TestCase
from django.template import engines

from core.exceptions import MissingAPIKeyError, APICommunicationError
from core.types import (
    AIComparisonResponse,
    AIMessage,
)
from api.utils.clientsIA import (
    APIClient,
    register_ai_client,
    AI_CLIENT_MAPPING,
)

# --- Classes Dummy para testes ---

class DummyPromptConfig:
    """Dummy para simular prompt_config."""
    def __init__(self, system_message, user_message, response):
        self.system_message = system_message
        self.user_message = user_message
        self.response = response

class DummyAIConfig:
    """Dummy para simular AIConfig."""
    def __init__(self, api_key="dummy-key", api_url="http://dummy", model_name="dummy-model",
                 configurations=None, use_system_message=True, training_configurations=None, prompt_config=None):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.configurations = configurations or {}
        self.use_system_message = use_system_message
        self.training_configurations = training_configurations or {}
        self.prompt_config = prompt_config

# Criando uma classe dummy para testar os métodos abstratos
class DummyAPIClient(APIClient):
    """Classe dummy que implementa os métodos abstratos de APIClient para testes."""
    name = "DummyAPI"
    can_train = True

    def _call_api(self, prompts: AIMessage) -> AIComparisonResponse:
        """Simula chamada de API retornando resposta fixa."""
        # Simula um tempo de processamento
        time.sleep(0.1)
        return AIComparisonResponse(
            response="dummy response",
            model_name=self.model_name,
            configurations=self.configurations,
            processing_time=0.1,
            error=None
        )

    def _prepare_train(self, file: Any) -> str:
        """Simula preparação de dados de treinamento."""
        return "dummy training data"

    def _start_training(self, training_data: str) -> AIComparisonResponse:
        """Simula início de treinamento."""
        return AIComparisonResponse(
            job_id=str(uuid.uuid4()),
            status="in_progress",
            model_name=None,
            error=None,
            processing_time=0.2
        )

    def get_training_status(self, job_id: str) -> AIComparisonResponse:
        """Simula obtenção de status de treinamento."""
        return AIComparisonResponse(
            job_id=job_id,
            status="completed",
            model_name="trained-dummy-model",
            error=None,
            processing_time=0.3
        )

    def _call_train_api(self, training_data: str) -> Any:
        """Não implementado para este dummy."""
        raise NotImplementedError("Não implementado neste dummy")

    def delete_trained_model(self, model_name: str) -> Any:
        """Simula remoção de modelo treinado."""
        return type("DummySuccess", (), {"success": True})

    def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True):
        """Simula listagem de modelos."""
        # Retorna uma lista simples de dicionários
        return [{"id": "model1", "name": "Modelo 1", "is_fine_tuned": False}]

    def api_list_files(self):
        """Simula listagem de arquivos."""
        # Retorna uma lista vazia para teste
        return type("DummyFiles", (), {"data": []})

    def delete_file(self, file_id: str) -> Any:
        """Simula remoção de arquivo."""
        return type("DummySuccess", (), {"success": True})


class RegisterAiClientTest(TestCase):
    """Testa a função register_ai_client e o mapeamento global de clientes."""

    def test_register_ai_client_decorator(self):
        """Verifica se uma classe decorada é registrada no AI_CLIENT_MAPPING."""
        @register_ai_client
        class TestClient(APIClient):
            name = "TestClient"
            def _call_api(self, prompts: AIMessage) -> AIComparisonResponse:
                raise NotImplementedError()
            def _prepare_train(self, file: Any) -> Any:
                raise NotImplementedError()
            def _start_training(self, training_data: Any) -> AIComparisonResponse:
                raise NotImplementedError()
            def get_training_status(self, job_id: str) -> AIComparisonResponse:
                raise NotImplementedError()
            def delete_trained_model(self, model_name: str) -> Any:
                raise NotImplementedError()
            def api_list_models(self, list_trained_models: bool = True, list_base_models: bool = True):
                return []
            def api_list_files(self):
                return []
            def delete_file(self, file_id: str) -> Any:
                return None

        self.assertIn("TestClient", AI_CLIENT_MAPPING)
        self.assertEqual(AI_CLIENT_MAPPING["TestClient"], TestClient)

class APIClientInitTest(TestCase):
    """Testa a inicialização da classe APIClient."""

    def test_init_without_api_key_raises(self):
        """Verifica se a ausência de api_key dispara MissingAPIKeyError."""
        dummy_config = DummyAIConfig(api_key="")
        with self.assertRaises(MissingAPIKeyError):
            DummyAPIClient(dummy_config)

    def test_render_template_success(self):
        """Testa o método _render_template com template simples."""
        dummy_config = DummyAIConfig()
        client = DummyAPIClient(dummy_config)
        template_str = "Olá, {{ name }}!"
        context = {"name": "Mundo"}
        rendered = client._render_template(template_str, context)
        self.assertEqual(rendered.strip(), "Olá, Mundo!")

class PreparePromptsTest(TestCase):
    """Testa o método _prepare_prompts de APIClient."""

    def test_prepare_prompts_with_system_message(self):
        """Verifica se _prepare_prompts prepara mensagens separadas se usar system_message."""
        prompt_config = DummyPromptConfig("Sistema: {{ ai_name }}", "Usuário: {{ ai_name }}", "Resposta")
        dummy_config = DummyAIConfig(prompt_config=prompt_config)
        client = DummyAPIClient(dummy_config)
        # Cria um dummy data (simula AISingleComparisonData) como um objeto simples
        dummy_data = type("DummyData", (), {"instructor": {"text": "instrutor"}, "student": {"text": "aluno"}})()
        message = client._prepare_prompts(dummy_data)
        # Verifica se o system_message e user_message foram renderizados (substituindo {{ ai_name }} por client.name)
        self.assertIn(client.name, message.system_message)
        self.assertIn(client.name, message.user_message)

class CompareMethodTest(TestCase):
    """Testa o método compare de APIClient."""

    def test_compare_calls_prepare_and_api(self):
        """Verifica se compare retorna a resposta do _call_api e os prompts usados."""
        prompt_config = DummyPromptConfig("Sistema: {{ ai_name }}", "Usuário: {{ ai_name }}", "Resposta")
        dummy_config = DummyAIConfig(prompt_config=prompt_config)
        client = DummyAPIClient(dummy_config)
        dummy_data = type("DummyData", (), {"instructor": {"info": "x"}, "student": {"info": "y"}})()
        response, message = client.compare(dummy_data)
        self.assertEqual(response.response, "dummy response")
        self.assertEqual(client.model_name, dummy_config.model_name)
        self.assertIsInstance(message, AIMessage)

# Fim de test_clientsIA.py
