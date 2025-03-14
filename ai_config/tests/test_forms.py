from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import UserToken
from ai_config.models import AIClientGlobalConfiguration, AIClientConfiguration
from ai_config.forms import AIClientConfigurationForm, UserAITrainingFileForm, AIClientTrainingForm
from core.validators import validate_training_data

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
