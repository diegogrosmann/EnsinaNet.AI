import logging
from django.http import JsonResponse
from .exceptions import APIClientError, FileProcessingError

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    """
    Middleware para capturar exceções globais e retornar respostas JSON apropriadas
    apenas para requisições que esperam respostas JSON (e.g., APIs).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
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
            
            # Verifica se a requisição espera JSON
            if request.headers.get('Accept') == 'application/json' or request.path.startswith('/api/'):
                return JsonResponse({"error": "Erro interno do servidor."}, status=500)
            else:
                # Re-raise a exceção para que o Django trate normalmente
                raise
