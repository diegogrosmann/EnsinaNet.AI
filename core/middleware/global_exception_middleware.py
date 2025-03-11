# core/middleware/global_exception_middleware.py

import logging
import time
import json
import traceback
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from django.conf import settings

from core.exceptions import ApplicationError  # Importa a exceção base do projeto

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    """
    Middleware global de exceções para toda a aplicação.
    Captura exceções não tratadas e retorna respostas apropriadas sem expor detalhes técnicos em produção.
    """

    def __init__(self, get_response):
        """
        Inicializa o middleware.
        Args:
            get_response: Função que processa a requisição.
        """
        self.get_response = get_response

    def is_ajax(self, request):
        """
        Verifica se a requisição é AJAX ou se espera resposta JSON.
        """
        return (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.content_type == 'application/json'
            or request.headers.get('Accept') == 'application/json'
            or request.path.startswith('/api/')
        )

    def format_error_response(self, error, status_code=500):
        """
        Formata a resposta de erro de forma padronizada.
        Em produção, retorna uma mensagem genérica.
        """
        generic_error_message = "Erro interno do servidor. Por favor, tente novamente mais tarde."
        if not settings.DEBUG:
            if status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                message = generic_error_message
            else:
                message = str(error)
        else:
            message = str(error)
        return {
            'success': False,
            'error': {
                'message': message,
                'type': error.__class__.__name__,
                'code': status_code
            }
        }

    def __call__(self, request):
        """
        Processa a requisição e captura exceções.
        Retorna uma JsonResponse (para requisições AJAX) ou redireciona com mensagem para requisições normais.
        """
        try:
            response = self.get_response(request)
            return response

        except (ApplicationError, PermissionDenied, ValidationError) as e:
            # Erros conhecidos (nossas exceções ou erros de validação/permissão)
            logger.warning(f"Erro conhecido: {str(e)}", exc_info=True)
            error_response = self.format_error_response(e, status.HTTP_400_BAD_REQUEST)
            if self.is_ajax(request):
                return JsonResponse(error_response, status=status.HTTP_400_BAD_REQUEST)
            else:
                messages.error(request, error_response['error']['message'])
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        except Exception as e:
            # Erros não tratados
            logger.error(
                "Erro não tratado no GlobalExceptionMiddleware",
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
                messages.error(request, 'Ocorreu um erro inesperado. Nossa equipe foi notificada.')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
