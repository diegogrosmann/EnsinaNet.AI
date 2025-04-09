"""
Middleware para monitoramento de requisições da API.

Este middleware registra métricas de uso, incluindo tempo de execução, dados da requisição/resposta,
e informações do token do usuário, armazenando os dados em logs e no banco de dados.
"""

import logging
import time
from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from accounts.models import UserToken
from api.models import APILog

logger = logging.getLogger(__name__)

class MonitoringMiddleware(MiddlewareMixin):
    """Monitora e registra métricas de uso da API.

    Este middleware captura o tempo de início da requisição, armazena o corpo da requisição e,
    ao final, registra informações detalhadas sobre a requisição e resposta, incluindo tempo de execução,
    status HTTP e IP do solicitante.

    Args:
        get_response (Callable): Função para processar a requisição.
    """

    def __init__(self, get_response: Callable) -> None:
        super().__init__(get_response)
        self.get_response = get_response

    def process_request(self, request: HttpRequest) -> None:
        """Marca o início da requisição e armazena o corpo.

        Args:
            request (HttpRequest): Objeto da requisição HTTP.
        """
        request.start_time = time.time()
        try:
            request._body = request.body
        except Exception:
            # Algumas requisições podem não ter corpo
            pass

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Processa e registra métricas da resposta.

        Registra no banco de dados informações como usuário, token, caminho, método, corpo da requisição,
        corpo da resposta, status HTTP, tempo de execução e IP do solicitante.

        Args:
            request (HttpRequest): Objeto da requisição HTTP.
            response (HttpResponse): Objeto da resposta HTTP.

        Returns:
            HttpResponse: A mesma resposta recebida.
        """
        try:
            # Calcular o tempo de execução se houver um tempo de início
            if hasattr(request, 'start_time'):
                execution_time = time.time() - request.start_time
            else:
                execution_time = 0.0
            
            # Extrair informações do token se existir
            token = None
            user = None
            auth_header = request.headers.get('Authorization', '')
            
            if auth_header.startswith('Token '):
                token_key = auth_header.replace('Token ', '')
                try:
                    token = UserToken.objects.select_related('user').get(key=token_key)
                    user = token.user
                except UserToken.DoesNotExist:
                    pass
            
            # Preparar dados para o log
            body = getattr(request, '_body', b'').decode('utf-8', errors='replace') if hasattr(request, '_body') else None
            response_content = response.content.decode('utf-8', errors='replace') if hasattr(response, 'content') else None
            
            # Criar o registro de log
            APILog.create_from_request(
                request=request,
                response=response,
                execution_time=execution_time
            )
            
            # Logging adicional para depuração
            logger.debug(
                f"API Request: {request.method} {request.path} - "
                f"Status: {response.status_code} - "
                f"Time: {execution_time:.3f}s - "
                f"User: {user.username if user else 'Anonymous'}"
            )

        except Exception as e:
            logger.exception(f"Erro ao registrar métricas de API: {str(e)}")

        return response
