from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from accounts.models import UserToken
from ai_config.models import AIClientGlobalConfiguration, AIClientConfiguration

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
        self.assertRedirects(response, reverse('ai_config:ai_config_manage', args=[self.token.id]))
        self.assertTrue(AIClientConfiguration.objects.filter(name='CFG1').exists())
