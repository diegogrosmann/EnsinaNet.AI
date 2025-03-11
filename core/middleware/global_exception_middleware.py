"""Middleware global para tratamento de exceções.

Fornece um mecanismo centralizado para capturar e tratar exceções
de forma consistente em toda a aplicação.
"""

import logging
import time
import json
import traceback
import uuid
from typing import Any, Dict, Optional

from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from django.conf import settings

from core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:
    """Middleware para tratamento centralizado de exceções.
    
    Captura exceções não tratadas e retorna respostas apropriadas
    sem expor detalhes técnicos em produção.
    """

    def __init__(self, get_response):
        """Inicializa o middleware.
        
        Args:
            get_response: Callable que processa a requisição.
        """
        self.get_response = get_response

    def _is_ajax(self, request: HttpRequest) -> bool:
        """Verifica se a requisição é AJAX/JSON.
        
        Args:
            request: Objeto de requisição HTTP.
            
        Returns:
            bool: True se for AJAX/JSON, False caso contrário.
        """
        return any([
            request.headers.get('X-Requested-With') == 'XMLHttpRequest',
            request.content_type == 'application/json',
            request.headers.get('Accept') == 'application/json',
            request.path.startswith('/api/')
        ])

    def _format_error_response(self, 
                             error: Exception, 
                             error_id: str,
                             status_code: int = 500) -> Dict[str, Any]:
        """Formata a resposta de erro de forma padronizada.
        
        Args:
            error: Exceção capturada.
            error_id: Identificador único do erro.
            status_code: Código HTTP do erro.
            
        Returns:
            Dict com a resposta formatada.
        """
        if settings.DEBUG:
            message = str(error)
            details = {
                'error_id': error_id,
                'type': error.__class__.__name__,
                'traceback': traceback.format_exc()
            }
        else:
            message = (
                str(error) if status_code != 500
                else "Erro interno do servidor. Por favor, tente novamente mais tarde."
            )
            details = {}

        return {
            'success': False,
            'error': {
                'message': message,
                'code': status_code,
                **details
            }
        }

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Processa a requisição e trata exceções.
        
        Args:
            request: Objeto de requisição HTTP.
            
        Returns:
            HttpResponse: Resposta HTTP apropriada.
        """
        try:
            response = self.get_response(request)
            return response

        except (ApplicationError, PermissionDenied, ValidationError) as e:
            error_id = str(uuid.uuid4())
            logger.warning(
                f"Erro conhecido (ID: {error_id}): {str(e)}", 
                exc_info=True,
                extra={'request_path': request.path}
            )
            
            status_code = getattr(e, 'status_code', 400)
            error_response = self._format_error_response(e, error_id, status_code)
            
            if self._is_ajax(request):
                return JsonResponse(error_response, status=status_code)
            
            messages.error(request, error_response['error']['message'])
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        except Exception as e:
            error_id = str(uuid.uuid4())
            logger.error(
                f"Erro não tratado (ID: {error_id})",
                exc_info=True,
                extra={
                    'request_path': request.path,
                    'request_method': request.method,
                }
            )
            
            error_response = self._format_error_response(
                e, 
                error_id,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
            if self._is_ajax(request):
                return JsonResponse(
                    error_response, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            messages.error(
                request, 
                'Ocorreu um erro inesperado. Nossa equipe foi notificada.'
            )
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
