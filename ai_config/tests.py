from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.forms import formset_factory

from accounts.models import UserToken
from ai_config.models import (
    AIClientGlobalConfiguration,
    AIClientConfiguration,
    AITrainingFile,
    TokenAIConfiguration,
    AIClientTraining
)
from ai_config.forms import (
    AIClientConfigurationForm,
    UserAITrainingFileForm,
    AIClientConfigurationForm,
    AIClientTrainingForm,
    AITrainingFileForm
)

#
# Testes de views (ManageAIConfigurationsViewTest, CreateAIConfigurationViewTest, etc.)
#
class ManageAIConfigurationsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='user3', email='user3@example.com', password='pass3')
        self.token = UserToken.objects.create(user=self.user, name="Token3")
        self.global_conf = AIClientGlobalConfiguration.objects.create(
            name="OpenAI",
            api_client_class="OpenAi",
            api_url="https://api.openai.com",
            api_key="dummy"
        )
        self.ai_config = AIClientConfiguration.objects.create(
            token=self.token,
            ai_client=self.global_conf,
            name='Config01',
            enabled=True
        )
        self.url = reverse('ai_config:manage_ai_configurations', args=[self.token.id])

    def test_view_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_view_list_configs(self):
        self.client.login(username='user3@example.com', password='pass3')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Config01')
        self.assertContains(response, 'OpenAI')


class CreateAIConfigurationViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u_c@example.com', email='u_c@example.com', password='pass_c')
        self.token = UserToken.objects.create(user=self.user, name="TokenC")
        self.global_conf = AIClientGlobalConfiguration.objects.create(
            name="TestAI",
            api_client_class="OpenAi",
            api_url="https://api.openai.com",
            api_key="dummy_key"
        )
        self.url = reverse('ai_config:create_ai_configuration', args=[self.token.id])
        self.client.login(username='user_c@example.com', password='pass_c')

    def test_create_configuration(self):
        self.client.login(username='u_c@example.com', password='pass_c')
        data = {
            'name': 'CFG1',
            'ai_client': self.global_conf.id,
            'enabled': True,
            'model_name': 'gpt-4',
            'configurations': 'temperature=0.5\nmax_tokens=1000'
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('ai_config:manage_ai_configurations', args=[self.token.id]))
        self.assertTrue(AIClientConfiguration.objects.filter(name='CFG1').exists())


#
# Testes de models (AIClientGlobalConfiguration, AITrainingFile, TokenAIConfiguration etc.)
#
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


#
# Testes de forms (AIClientConfigurationFormTest, etc.)
#
class AIClientConfigurationFormTest(TestCase):
    def setUp(self):
        self.global_conf = AIClientGlobalConfiguration.objects.create(
            name="OpenAI",
            api_client_class="OpenAi",
            api_url="https://api.openai.com",
            api_key="123"
        )
        self.user = User.objects.create_user(username='user1', email='u1@example.com', password='pass')
        self.token = UserToken.objects.create(user=self.user, name="Token1")

    def test_configurations_parsing(self):
        data = {
            'name': 'CFG1',
            'ai_client': self.global_conf.id,
            'enabled': True,
            'model_name': 'gpt-4',
            'configurations': 'temperature=0.5\nmax_tokens=1000'
        }
        form = AIClientConfigurationForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)
        obj.token = self.token
        obj.save()
        self.assertEqual(obj.configurations, {'temperature': 0.5, 'max_tokens': 1000})


#
# Exemplo de teste simples adicional, se desejar
# (já coberto em createAiConfigurationViewTest e manageAiConfigurationsViewTest)
#

class AIClientTrainingFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='userf', email='uf@example.com', password='pf')
        self.token = UserToken.objects.create(user=self.user, name="token_f")
        self.global_conf = AIClientGlobalConfiguration.objects.create(
            name="OpenAIForm",
            api_client_class="OpenAi",
            api_url="https://api.openai.com",
            api_key="fakekey"
        )
        self.ai_conf = AIClientConfiguration.objects.create(
            token=self.token,
            ai_client=self.global_conf,
            name='AIConfForm',
            enabled=True
        )

    def test_training_form(self):
        training_data = {
            'training_parameters': 'epoch=5\nlr=0.001'
        }
        form = AIClientTrainingForm(data=training_data)
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.ai_client_configuration = self.ai_conf
        instance.save()
        self.assertEqual(instance.training_parameters, {'epoch': 5, 'lr': 0.001})


class UserAITrainingFileFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='usertf', email='usertf@example.com', password='passf')

    def test_upload_training_file_form(self):
        form_data = {}
        form_files = {'file': None}  # Por exemplo
        form = UserAITrainingFileForm(data=form_data, files=form_files)
        self.assertFalse(form.is_valid())
        # Precisaria simular upload real se quiser testar integralmente
