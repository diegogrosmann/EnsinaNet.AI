"""
Módulo que contém middlewares globais para a API.

Classes:
    GlobalExceptionMiddleware: Captura exceções e retorna JSON apropriado.
    MonitoringMiddleware: Registra logs de cada requisição, para uso no painel de monitoramento.
"""

import logging
import time
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .exceptions import APIClientError, FileProcessingError
from api.models import APILog
from accounts.models import UserToken

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    """
    Middleware para capturar exceções globais e retornar respostas JSON
    apropriadas para APIs.
    """

    def __init__(self, get_response):
        """Inicializa o middleware.

        Args:
            get_response (Callable): Próximo middleware ou view.
        """
        self.get_response = get_response

    def __call__(self, request):
        """Processa a requisição e captura exceções.

        Args:
            request (HttpRequest): A requisição.
        
        Returns:
            HttpResponse: Resposta do próximo middleware ou view.
        """
        try:
            response = self.get_response(request)
            return response
        except APIClientError as e:
            logger.error(f"Erro do cliente de API: {e}")
            return JsonResponse({"error": str(e)}, status=500)
        except FileProcessingError as e:
            logger.error(f"Erro no processamento de arquivos: {e}")
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            logger.exception("Erro inesperado:")
            # Se for requisição com Accept JSON ou rota /api/, retorne JSON
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({"error": "Erro interno do servidor."}, status=500)
            else:
                raise


class MonitoringMiddleware(MiddlewareMixin):
    """
    Middleware que registra logs de uso da API para fins de monitoramento.
    Mede o tempo de execução e grava um APILog no banco de dados.
    """

    def process_request(self, request):
        """
        Armazena o tempo de início no request, para calcular a duração depois.
        """
        request._monitoring_start_time = time.time()

    def process_response(self, request, response):
        """
        Ao finalizar a requisição, calcula o tempo total e salva no APILog,
        caso seja uma rota de /api/.

        (NOVO) Agora também salva o campo 'user' em APILog.
        """
        try:
            start_time = getattr(request, '_monitoring_start_time', None)
            if start_time is not None:
                elapsed = time.time() - start_time
            else:
                elapsed = 0.0

            if request.path.startswith('/api/'):
                user_token = None
                user = None

                auth_header = request.META.get('HTTP_AUTHORIZATION', '')
                if auth_header.startswith('Token '):
                    key = auth_header.replace('Token ', '')
                    try:
                        user_token = UserToken.objects.get(key=key)
                        user = user_token.user  # (NOVO) Salva o usuário do token
                    except UserToken.DoesNotExist:
                        user_token = None
                        user = None
                else:
                    # Se tiver request.user e estiver autenticado, podemos usá-lo
                    if request.user.is_authenticated:
                        user = request.user

                APILog.objects.create(
                    user=user,  # (NOVO)
                    user_token=user_token,
                    path=request.path,
                    method=request.method,
                    status_code=getattr(response, 'status_code', 0),
                    execution_time=round(elapsed, 4),
                )
        except Exception as e:
            logger.error(f"Erro ao salvar APILog: {e}")

        return response
