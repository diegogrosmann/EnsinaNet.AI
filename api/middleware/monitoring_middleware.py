"""Middleware para monitoramento de requisições da API."""

import logging
import time
from typing import Optional, Callable, Any
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from accounts.models import UserToken
from api.models import APILog
from core.types import APILog as APILogType

logger = logging.getLogger(__name__)

class MonitoringMiddleware(MiddlewareMixin):
    """Monitora e registra métricas de uso da API."""

    def __init__(self, get_response: Callable) -> None:
        super().__init__(get_response)
        self.get_response = get_response

    def process_request(self, request: HttpRequest) -> None:
        """Marca o início da requisição e armazena o corpo."""
        request.start_time = time.time()
        # Armazena o corpo da requisição antes que seja consumido
        try:
            request._body = request.body
        except Exception:
            request._body = None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Processa e registra métricas da resposta."""
        try:
            # Extrai token se presente
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            token_key = auth_header.split(' ')[-1] if ' ' in auth_header else None
            
            # Busca token se existir
            user_token: Optional[UserToken] = None
            if token_key:
                try:
                    user_token = UserToken.objects.get(key=token_key)
                except UserToken.DoesNotExist:
                    pass

            # Calcula tempo de execução
            execution_time = time.time() - getattr(request, 'start_time', time.time())
            
            # Usa o corpo armazenado
            request_body = getattr(request, '_body', None)
            if request_body:
                request_body = request_body.decode() if isinstance(request_body, bytes) else str(request_body)
            
            # Cria log
            APILog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                user_token=user_token,
                path=request.path,
                method=request.method,
                request_body=request_body,
                response_body=response.content.decode() if response.content else None,
                status_code=response.status_code,
                execution_time=round(execution_time, 3),
                requester_ip=request.META.get('REMOTE_ADDR')
            )

        except Exception as e:
            logger.error(f"Erro ao registrar métricas: {e}")

        return response
