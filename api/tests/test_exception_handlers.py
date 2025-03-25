# ai_config/tests/test_exception_handlers.py

import json
import uuid
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpRequest
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.views import exception_handler
from rest_framework import status
from api.exception_handlers import custom_exception_handler
from core.exceptions import APIError, ApplicationError
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework.test import APIRequestFactory

class CustomExceptionHandlerTest(TestCase):
    """Testes para o manipulador customizado de exceções da API."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.context = {'view': APIView()}

    def _prepare_response(self, response):
        """Prepara a resposta adicionando o renderizador necessário para o teste."""
        if response:
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/json"
            response.renderer_context = {}
        return response

    def test_handler_validation_error(self):
        """Testa se ValidationError é tratado corretamente."""
        validation_error = ValidationError({"field": "Erro de validação"})
        request = self.factory.get('/fake-url/')
        self.context['request'] = request
        
        response = custom_exception_handler(validation_error, self.context)
        response = self._prepare_response(response)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("field", response.data['error'])

    def test_handler_authentication_failed(self):
        """Testa se AuthenticationFailed retorna status 401."""
        auth_error = AuthenticationFailed("Credenciais inválidas")
        request = self.factory.get('/fake-url/')
        self.context['request'] = request
        
        response = custom_exception_handler(auth_error, self.context)
        response = self._prepare_response(response)
        
        self.assertEqual(response.status_code, 401)
        self.assertIn("Credenciais", response.data['error'])

    def test_handler_generic_exception(self):
        """Testa se uma exceção genérica retorna status 500."""
        generic_error = Exception("Erro interno")
        request = self.factory.get('/fake-url/')
        self.context['request'] = request
        
        response = custom_exception_handler(generic_error, self.context)
        response = self._prepare_response(response)
        
        self.assertEqual(response.status_code, 500)
        self.assertIn("Erro interno do servidor", response.data['error'])

# Fim de test_exception_handlers.py
