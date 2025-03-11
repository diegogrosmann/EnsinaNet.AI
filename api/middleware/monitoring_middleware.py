# api/middleware/monitoring_middleware.py

import logging
import time
from django.utils.deprecation import MiddlewareMixin
from accounts.models import UserToken
from api.models import APILog

logger = logging.getLogger(__name__)

class MonitoringMiddleware(MiddlewareMixin):
    """
    Middleware para monitoramento de requisições da API.
    Registra logs de uso da API, incluindo tempo de execução e dados do token.
    Este middleware deve ser aplicado apenas aos endpoints da API.
    """

    def process_request(self, request):
        """
        Marca o início do processamento da requisição.
        """
        request.start_time = time.time()

    def process_response(self, request, response):
        """
        Registra o log da requisição após seu processamento.
        """
        if hasattr(request, 'start_time'):
            execution_time = time.time() - request.start_time
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            token_key = auth_header.split(' ')[-1] if ' ' in auth_header else ''
            try:
                user_token = UserToken.objects.get(key=token_key) if token_key else None
                user = user_token.user if user_token else None
                APILog.objects.create(
                    user=user,
                    user_token=user_token,
                    path=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    execution_time=execution_time
                )
            except Exception as e:
                logger.error(f"Erro ao criar log de monitoramento: {e}")
        return response
