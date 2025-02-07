import logging
from django.http import JsonResponse
from .exceptions import APIClientError, FileProcessingError

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    """Middleware para capturar exceções globais e retornar respostas JSON apropriadas para APIs."""
    
    def __init__(self, get_response):
        """Inicializa o middleware.

        Args:
            get_response (Callable): Função de resposta do próximo middleware.
        """
        self.get_response = get_response

    def __call__(self, request):
        """Processa a requisição e captura exceções.

        Args:
            request (HttpRequest): Requisição HTTP.

        Returns:
            JsonResponse: Resposta HTTP adequada para a requisição.

        Raises:
            Exception: Quando a exceção não for tratada e precisar ser repassada ao Django.
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
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({"error": "Erro interno do servidor."}, status=500)
            else:
                raise
