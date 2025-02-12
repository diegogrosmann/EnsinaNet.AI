from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from api.models import APILog
from accounts.models import UserToken
from api.utils.doc_extractor import extract_text, FileProcessingError
from api.utils.circuit_breaker import (
    attempt_call,
    record_failure,
    record_success,
    CIRCUIT_STATE,
    CircuitOpenError
)

#
# Testes de middleware (MonitoringMiddlewareTest)
#
class MonitoringMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mwuser', email='mw@example.com', password='pass')
        self.token = UserToken.objects.create(user=self.user, name='mwtoken')

    def test_monitoring_log_created(self):
        url = reverse('api.v1:compare')
        self.client.post(url, {}, HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertTrue(APILog.objects.exists())

    def test_monitoring_log_anonymous(self):
        url = reverse('api.v1:compare')
        self.client.post(url, {})
        self.assertTrue(APILog.objects.exists())
        self.assertIsNone(APILog.objects.first().user_token)


#
# Testes de circuit_breaker (CircuitBreakerTest)
#
class CircuitBreakerTest(TestCase):
    def setUp(self):
        CIRCUIT_STATE.clear()

    def test_circuit_breaker_flow(self):
        client_name = "OpenAi"

        # 1) Sucesso direto
        attempt_call(client_name)  # Nao deve lançar exceção
        record_success(client_name)

        # 2) Falhas sucessivas
        record_failure(client_name)
        record_failure(client_name)
        record_failure(client_name)

        # Nesse ponto o circuito deve estar 'open'
        with self.assertRaises(CircuitOpenError):
            attempt_call(client_name)


#
# Testes de utils (DocExtractorTest)
#
class DocExtractorTest(TestCase):
    def test_extract_text_file_missing(self):
        with self.assertRaises(FileProcessingError):
            extract_text({})  # dados incompletos

    def test_extract_text_unsupported_format(self):
        data = {
            "name": "file.txt",
            "content": "Zm9vYmFy"  # base64('foobar')
        }
        with self.assertRaises(FileProcessingError):
            extract_text(data)


#
# Testes de models (APILogModelTest)
#
class APILogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", "test@example.com", "pass")
        self.token = UserToken.objects.create(user=self.user, name="testtoken")

    def test_create_api_log(self):
        log = APILog.objects.create(
            user=self.user,
            user_token=self.token,
            path='/api/test/',
            method='GET',
            status_code=200,
            execution_time=0.123,
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.user_token, self.token)
        self.assertIn("/api/test/", str(log))


#
# Testes de views (CompareAPITest)
#
class CompareAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('u4', 'u4@example.com', 'pass4')
        self.token = UserToken.objects.create(user=self.user, name='t4')
        self.client = APIClient()
        # URL do compare -> /api/v1/compare/
        self.compare_url = reverse('api.v1:compare')

    def test_compare_invalid_token(self):
        response = self.client.post(self.compare_url, {}, HTTP_AUTHORIZATION='Token INVALID')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Token inválido', str(response.data))

    def test_compare_missing_fields(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.compare_url, {})
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)

    def test_compare_success(self):
        from ai_config.models import TokenAIConfiguration
        TokenAIConfiguration.objects.create(token=self.token, prompt='prompt base')

        data = {
            "instructor": {"foo": "bar"},  # Exemplo simples
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
