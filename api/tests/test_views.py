"""Testes para as views da API."""

from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
import json
import base64

from accounts.models import UserToken
from ai_config.models import (
    AIClientConfiguration, 
    AIClientGlobalConfiguration, 
    TokenAIConfiguration
)

class TestCompareView(APITestCase):
    def setUp(self):
        """Configura o ambiente de teste."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.token = UserToken.objects.create(
            user=self.user,
            name="TestToken"
        )

        # Criar configuração global de IA
        self.global_config = AIClientGlobalConfiguration.objects.create(
            name="Test AI",
            api_client_class="OpenAi",
            api_key="test-key"
        )

        # Criar configuração de IA para o token
        self.ai_config = AIClientConfiguration.objects.create(
            token=self.token,
            ai_client=self.global_config,
            name="Test Config",
            enabled=True
        )

        # Criar configuração de token AI
        self.token_config = TokenAIConfiguration.objects.create(
            token=self.token,
            base_instruction="Test instruction",
            prompt="Test prompt"
        )

        # Configurar cliente de teste
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_compare_valid_request(self):
        """Testa uma requisição válida."""
        url = reverse('api_v1:compare')
        
        # Dados de exemplo para a comparação
        data = {
            "instructor": {
                "foo": "Dados do instrutor"
            },
            "students": {
                "student1": {
                    "bar": "Dados do estudante 1"
                },
                "student2": {
                    "bar": "Dados do estudante 2"
                }
            }
        }

        response = self.client.post(url, data=data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('students', response.json())

    def test_compare_view_invalid_token(self):
        """Testa autenticação com token inválido."""
        url = reverse('api_v1:compare')
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid-token')
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
