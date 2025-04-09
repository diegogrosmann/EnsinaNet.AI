"""
Middleware global para tratamento centralizado de exceções.

Fornece um mecanismo centralizado para capturar e tratar exceções de forma consistente em toda a aplicação,
garantindo logs padronizados e respostas apropriadas ao usuário sem expor detalhes técnicos.
"""

import logging
import traceback
import uuid


from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse
from django.contrib import messages
from rest_framework import status
from django.conf import settings

from core.exceptions import AppException
from core.types import JSONDict

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

    def _format_error_response(self, error: Exception, error_id: str, status_code: int = 500, detail: str = None) -> JSONDict:
        """Formata a resposta de erro de forma padronizada.

        Em modo DEBUG, inclui detalhes como traceback; caso contrário, retorna mensagem genérica para erros internos.

        Args:
            error: Exceção ocorrida.
            error_id: Identificador único do erro para rastreamento.
            status_code: Código HTTP de status para a resposta.

        Returns:
            JSONDict: Dicionário com a resposta formatada.
        """
        error_message = str(error)
        additional_data = {}
        
        if settings.DEBUG:
            additional_data['traceback'] = traceback.format_exc()
        
        if status_code >= 500 and not settings.DEBUG:
            # Em produção, esconder detalhes técnicos para erros de servidor
            error_message = f"Erro interno"
        
        error_detail = AppException(
            message=error_message,
            code=str(type(error)),
            error_id=error_id,
            status_code=status_code,
            additional_data=additional_data
        )
        
        return {
            'success': False,
            'error': error_detail.to_dict(),
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
        except Exception as e:
            # Gerar ID único para o erro (para rastreamento)
            error_id = str(uuid.uuid4())

            # Determinar a mensagem de erro, status_code e detail
            status_code = getattr(e, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
            detail = getattr(e, 'detail', str(e))
            error_message = str(e)

            # Log do erro
            logger.error(
                f"Erro tratado: {type(e).__name__} - {error_message} (ID: {error_id})",
                exc_info=True
            )

            # Determinar o tipo de resposta
            if self._is_ajax(request):
                # Retornar resposta JSON para APIs
                error_response = self._format_error_response(
                    e, error_id, status_code, detail
                )
                return JsonResponse(error_response, status=status_code)
            else:
                # Redirecionar com mensagem flash para interface web
                messages.error(request, f"{error_message} (ID: {error_id})")
                referer = request.META.get('HTTP_REFERER', '/')
                return HttpResponseRedirect(referer)
