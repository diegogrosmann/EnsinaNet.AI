"""Middlewares da API.

Este módulo contém os middlewares para tratamento de exceções e monitoramento
de requisições da API.
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
    """Middleware para tratamento global de exceções.
    
    Captura exceções não tratadas e retorna respostas JSON apropriadas.
    """

    def __init__(self, get_response):
        """Inicializa o middleware.
        
        Args:
            get_response: Função para processar a requisição.
        """
        self.get_response = get_response

    def __call__(self, request):
        """Processa a requisição e captura exceções.
        
        Args:
            request: Objeto da requisição HTTP.
            
        Returns:
            JsonResponse: Em caso de erro.
            HttpResponse: Resposta normal caso não haja erros.
        """
        try:
            response = self.get_response(request)
            return response
        except APIClientError as e:
            logger.error(f"Erro do cliente API: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            logger.exception("Erro não tratado no middleware global")
            return JsonResponse({"error": "Erro interno do servidor"}, status=500)

class MonitoringMiddleware(MiddlewareMixin):
    """Middleware para monitoramento de requisições.
    
    Registra logs de uso da API, incluindo tempo de execução.
    """

    def process_request(self, request):
        """Marca o início do processamento da requisição.
        
        Args:
            request: Objeto da requisição HTTP.
        """
        request.start_time = time.time()

    def process_response(self, request, response):
        """Registra o log da requisição após seu processamento.
        
        Args:
            request: Objeto da requisição HTTP.
            response: Objeto da resposta HTTP.
            
        Returns:
            HttpResponse: A mesma resposta recebida.
        """
        if hasattr(request, 'start_time'):
            execution_time = time.time() - request.start_time
            
            # Extrai o token da requisição
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
