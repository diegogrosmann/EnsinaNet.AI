import json
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.contrib.messages.storage.fallback import FallbackStorage
from api.utils.global_exception_middleware import GlobalExceptionMiddleware
from core.exceptions import ApplicationError

class DummyException(Exception):
    pass

def dummy_get_response(request):
    raise DummyException("Erro dummy para teste")

class GlobalExceptionMiddlewareTest(TestCase):
    """Testes para o middleware global de exceções."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GlobalExceptionMiddleware(dummy_get_response)

    @override_settings(DEBUG=True)
    def test_ajax_exception_debug(self):
        """Testa resposta JSON detalhada em requisição AJAX com DEBUG=True."""
        request = self.factory.get("/dummy/")
        request.META["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        # Necessário configurar mensagens no request
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertIn("Erro dummy para teste", data["error"]["message"])
        self.assertIn("traceback", data["error"])

    def test_non_ajax_exception(self):
        """Testa redirecionamento em requisição não-AJAX quando ocorre exceção."""
        request = self.factory.get("/dummy/", HTTP_REFERER="/previous/")
        # Simula usuário autenticado
        request.user = type("DummyUser", (), {"is_authenticated": True, "username": "testuser"})
        response = self.middleware(request)
        # Em não-AJAX, espera redirecionamento
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/previous/")
