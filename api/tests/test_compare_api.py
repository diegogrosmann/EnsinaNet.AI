"""Testes de integração para o endpoint de comparação da API.

Este módulo contém testes que verificam o funcionamento completo do endpoint /api/compare,
incluindo autenticação, validação de dados e processamento da comparação.
"""

from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
from django.contrib.auth.models import User

from accounts.models import UserToken
from api.models import APILog

class CompareAPITest(APITestCase):
    """Testes de integração do endpoint de comparação.
    
    Verifica o comportamento da API em diferentes cenários de uso.
    """

    def setUp(self):
        """Configura o ambiente de teste.
        
        Cria usuário e token para autenticação nos testes.
        """
        self.user = User.objects.create_user('u4', 'u4@example.com', 'pass4')
        self.token = UserToken.objects.create(user=self.user, name='t4')
        self.client = APIClient()
        # URL do compare -> /api/v1/compare/
        self.compare_url = reverse('api.v1:compare')

    def test_compare_invalid_token(self):
        """Testa rejeição de token inválido.
        
        Verifica se a API retorna 401 quando um token inválido é fornecido.
        """
        response = self.client.post(self.compare_url, {}, HTTP_AUTHORIZATION='Token INVALID')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Token inválido', str(response.data))

    def test_compare_missing_fields(self):
        """Testa validação de campos obrigatórios.
        
        Verifica se a API retorna 400 quando campos obrigatórios estão ausentes.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.compare_url, {})
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)

    def test_compare_success(self):
        """Testa cenário de sucesso na comparação.
        
        Verifica se a API processa corretamente uma requisição válida.
        """
        from ai_config.models import TokenAIConfiguration
        TokenAIConfiguration.objects.create(token=self.token, prompt='prompt base')

        data = {
            "instructor": {"foo": "bar"},
            "students": {
                "student1": {"data": "xpto"},
                "student2": {"data": "xyz"}
            }
        }
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.compare_url, data, format='json')
        # Se não houver erro, deve retornar 200
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('students', response_data)
        self.assertTrue(APILog.objects.exists())
