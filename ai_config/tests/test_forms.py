# ai_config/tests/test_forms.py

from django.test import TestCase
from ai_config.forms import (
    AIClientGlobalConfigForm,
    AIClientConfigurationForm,
    TokenAIConfigurationForm,
    AITrainingFileForm,
    TrainingCaptureForm
)
from ai_config.models import AIClientGlobalConfiguration, AIClientConfiguration, AITrainingFile
from accounts.models import User, UserToken
# Importar o mapeamento de clientes disponíveis
from api.utils.clientsIA import AI_CLIENT_MAPPING

class AIClientGlobalConfigFormTest(TestCase):
    """Testes para o formulário AIClientGlobalConfigForm."""

    def test_criar_config_global_valido(self):
        """Testa criação de configuração global válida."""
        # Obter uma das chaves disponíveis no mapeamento
        if not AI_CLIENT_MAPPING:
            self.skipTest("Nenhum cliente de IA registrado")
            
        client_class = list(AI_CLIENT_MAPPING.keys())[0]
        form_data = {
            'name': 'Configuração Teste',
            'api_client_class': client_class,  # Usa um cliente disponível
            'api_url': 'https://api.exemplo.com',
            'api_key': 'uma_chave_api_valida'
        }
        form = AIClientGlobalConfigForm(data=form_data)
        # Imprimir erros do formulário para debug se necessário
        if not form.is_valid():
            print(f"Erros de validação: {form.errors}")
            
        self.assertTrue(form.is_valid())

    def test_mascaramento_api_key(self):
        """Testa se a API key é mascarada apropriadamente em edição."""
        config = AIClientGlobalConfiguration.objects.create(
            name="Config Existente",
            api_client_class="FakeClient",
            api_url="http://api.com",
            api_key="abcd1234"
        )
        form = AIClientGlobalConfigForm(instance=config)
        self.assertIn("****", form.initial["api_key"])  # valor mascarado

class AIClientConfigurationFormTest(TestCase):
    """Testes para o formulário AIClientConfigurationForm."""

    def test_form_valido(self):
        """Testa se o formulário aceita dados válidos."""
        global_config = AIClientGlobalConfiguration.objects.create(
            name="Configuração Global de Teste",
            api_client_class="DummyModel",
            api_url="https://example.com/api",
            api_key="uma_chave_api_valida"  # Adicionando api_key válida
        )
        form_data = {
            "name": "Minha IA",
            "ai_client": global_config.id,
            "model_name": "gpt-3",
            "configurations": "temperature=0.5\ntop_k=50",
            "training_configurations": "batch_size=2\nepochs=3",
            "use_system_message": "on"  # Usando "on" para o checkbox
        }
        form = AIClientConfigurationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

class TokenAIConfigurationFormTest(TestCase):
    """Testes para o formulário TokenAIConfigurationForm."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="formtest",
            email="formtest@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(
            user=self.user, name="Form Token", key="xxxyyy"
        )

    def test_form_criacao_valido(self):
        """Testa criação de config de token com prompt e base_instruction."""
        form_data = {
            "base_instruction": "<b>Base!</b>",
            "prompt": "<script>alert('hello')</script>Olá!",
            "responses": "<i>Resposta</i>"
        }
        form = TokenAIConfigurationForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        config = form.save(commit=False)
        config.token = self.token
        config.save()
        self.assertIn("Base!", config.base_instruction)
        self.assertNotIn("<script>", config.prompt)

class AITrainingFileFormTest(TestCase):
    """Testes para o formulário AITrainingFileForm."""
    def test_form_invalido_sem_nome(self):
        """Testa se o formulário falha se não for informado 'name'."""
        form = AITrainingFileForm(data={})
        self.assertFalse(form.is_valid())

    def test_form_valido(self):
        """Testa se o formulário é válido com nome."""
        form = AITrainingFileForm(data={"name": "Treino 1"})
        self.assertTrue(form.is_valid())

class TrainingCaptureFormTest(TestCase):
    """Testes para o formulário TrainingCaptureForm."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="capture_user",
            email="capture_user@example.com",
            password="test123"
        )
        self.token = UserToken.objects.create(user=self.user, name="CaptureToken", key="abc")
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Teste Global Config",
            api_client_class="DummyModel",
            api_url="https://example.com/api",
            api_key="uma_chave_api_valida"  # Adicionando uma api_key válida
        )
        self.ai_config = AIClientConfiguration.objects.create(
            user=self.user,
            ai_client=self.global_config,
            name="AI config test"
        )

    def test_form_valido(self):
        """Testa se o formulário aceita dados válidos."""
        form_data = {
            "token": self.token.id,
            "ai_client_config": self.ai_config.id
        }
        form = TrainingCaptureForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
