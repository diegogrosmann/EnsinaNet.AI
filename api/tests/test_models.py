"""Testes para os modelos da API.

Este módulo contém testes para verificar o funcionamento correto
dos modelos da API, especialmente o APILog.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import UserToken
from api.models import APILog

class APILogModelTest(TestCase):
    """Testes para o modelo APILog.
    
    Verifica a criação e manipulação de registros de log da API.
    """

    def setUp(self):
        """Configura o ambiente de teste.
        
        Cria usuário e token necessários para os testes.
        """
        self.user = User.objects.create_user(username='testuser', 
                                           email='test@example.com', 
                                           password='testpass')
        self.token = UserToken.objects.create(user=self.user, name='Test Token')

    def test_create_api_log(self):
        """Testa a criação de um registro de log.
        
        Verifica se todos os campos são salvos corretamente
        e se os relacionamentos são mantidos.
        """
        log = APILog.objects.create(
            user=self.user,
            user_token=self.token,
            path='/api/test/',
            method='GET',
            status_code=200,
            execution_time=0.5
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.user_token, self.token)
        self.assertEqual(log.path, '/api/test/')
        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.execution_time, 0.5)
