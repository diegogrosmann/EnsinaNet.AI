"""
Middleware global para tratamento centralizado de exceções.

Fornece um mecanismo centralizado para capturar e tratar exceções de forma consistente em toda a aplicação,
garantindo logs padronizados e respostas apropriadas ao usuário sem expor detalhes técnicos.
"""

import logging
import traceback
import uuid
from typing import Any, Callable

from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from django.conf import settings

from core.exceptions import ApplicationError
from core.types.api_response import APIResponseDict
from core.types.base import JSONDict

logger = logging.getLogger(__name__)


class GlobalExceptionMiddleware:
    """Middleware para tratamento global de exceções.

    Captura exceções não tratadas e retorna respostas apropriadas sem expor detalhes técnicos,
    utilizando tratamento centralizado de exceções.

    Args:
        get_response (Callable): Função para processar a requisição.
    """

    def __init__(self, get_response):
        # Inicializa o middleware com a função de resposta da requisição
        self.get_response = get_response

    def _is_ajax(self, request: HttpRequest) -> bool:
        """Verifica se a requisição é do tipo AJAX/JSON.

        Args:
            request: Requisição HTTP a ser analisada.

        Returns:
            bool: True se a requisição for AJAX/JSON, False caso contrário.
        """
        return any([
            request.path.startswith('/api/'),
            request.headers.get('X-Requested-With') == 'XMLHttpRequest',
            request.content_type == 'application/json',
            'json' in (request.headers.get('Accept') or '').lower()
        ])

    def _format_error_response(self, error: Exception, error_id: str, status_code: int = 500) -> JSONDict:
        """Formata a resposta de erro de forma padronizada.

        Em modo DEBUG, inclui detalhes como traceback; caso contrário, retorna mensagem genérica para erros internos.

        Args:
            error: Exceção ocorrida.
            error_id: Identificador único do erro para rastreamento.
            status_code: Código HTTP de status para a resposta.

        Returns:
            JSONDict: Dicionário com a resposta formatada.
        """
        if settings.DEBUG:
            # Em modo debug, fornecer mais informações
            return {
                'success': False,
                'error': str(error),
                'error_id': error_id,
                'status_code': status_code,
                'traceback': traceback.format_exc()
            }
        else:
            # Em produção, esconder detalhes técnicos para erros de servidor
            error_message = str(error) if status_code < 500 else f"Erro interno (ID: {error_id})"
            return {
                'success': False,
                'error': error_message,
                'error_id': error_id,
                'status_code': status_code
            }

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Processa a requisição e trata exceções de forma centralizada.

        Args:
            request: Requisição HTTP a ser processada.

        Returns:
            HttpResponse: Resposta HTTP apropriada conforme o tipo de exceção.
        """
        try:
            return self.get_response(request)
        except (ApplicationError, PermissionDenied, ValidationError) as e:
            # Gerar ID único para o erro (para rastreamento)
            error_id = str(uuid.uuid4())
            
            # Determinar o status_code com base no tipo de erro
            if isinstance(e, PermissionDenied):
                status_code = status.HTTP_403_FORBIDDEN
            elif isinstance(e, ValidationError):
                status_code = status.HTTP_400_BAD_REQUEST
            else:
                status_code = getattr(e, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Log do erro
            logger.error(
                f"Erro tratado: {type(e).__name__} - {str(e)} (ID: {error_id})",
                exc_info=True
            )
            
            # Determinar o tipo de resposta
            if self._is_ajax(request):
                # Retornar resposta JSON para APIs
                error_response = self._format_error_response(e, error_id, status_code)
                return JsonResponse(error_response, status=status_code)
            else:
                # Redirecionar com mensagem flash para interface web
                messages.error(request, f"{str(e)} (ID: {error_id})")
                referer = request.META.get('HTTP_REFERER', '/')
                return HttpResponseRedirect(referer)
                
        except Exception as e:
            # Gerar ID único para o erro (para rastreamento)
            error_id = str(uuid.uuid4())
            
            # Log do erro não tratado
            logger.critical(
                f"Erro não tratado: {type(e).__name__} - {str(e)} (ID: {error_id})",
                exc_info=True
            )
            
            # Determinar o tipo de resposta
            if self._is_ajax(request):
                # Retornar resposta JSON para APIs
                error_response = self._format_error_response(
                    e, error_id, status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                return JsonResponse(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # Redirecionar com mensagem flash para interface web
                messages.error(
                    request, 
                    f"Ocorreu um erro interno. Nossa equipe foi notificada. (ID: {error_id})"
                )
                referer = request.META.get('HTTP_REFERER', '/')
                return HttpResponseRedirect(referer)
