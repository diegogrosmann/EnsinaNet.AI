"""Middlewares da API.

Este módulo contém os middlewares para tratamento de exceções e monitoramento
de requisições da API.
"""

import logging
import time
import json
import traceback
from django.http import JsonResponse, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status

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

    def is_ajax(self, request):
        """Verifica se a requisição é AJAX."""
        return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
               request.content_type == 'application/json' or \
               request.headers.get('Accept') == 'application/json' or \
               request.path.startswith('/api/')

    def format_error_response(self, error, status_code=500):
        """Formata a resposta de erro de maneira padronizada."""
        return {
            'success': False,
            'error': {
                'message': str(error),
                'type': error.__class__.__name__,
                'code': status_code
            }
        }

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
            # Erros conhecidos da API
            logger.warning(f"API Client Error: {str(e)}", exc_info=True)
            error_response = self.format_error_response(e, status.HTTP_400_BAD_REQUEST)
            return JsonResponse(error_response, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as e:
            # Erros de validação
            logger.warning(f"Validation Error: {str(e)}")
            error_response = self.format_error_response(e, status.HTTP_422_UNPROCESSABLE_ENTITY)
            return JsonResponse(error_response, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        except PermissionDenied as e:
            # Erros de permissão
            logger.warning(f"Permission Denied: {str(e)}")
            error_response = self.format_error_response(e, status.HTTP_403_FORBIDDEN)
            return JsonResponse(error_response, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            # Erros não tratados
            logger.error(
                "Erro não tratado no middleware global",
                exc_info=True,
                extra={
                    'request_path': request.path,
                    'request_method': request.method,
                    'traceback': traceback.format_exc()
                }
            )

            if self.is_ajax(request):
                error_response = self.format_error_response(
                    "Erro interno do servidor. Por favor, tente novamente mais tarde.",
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                return JsonResponse(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                messages.error(
                    request,
                    'Ocorreu um erro inesperado. Nossa equipe foi notificada.'
                )
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

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
