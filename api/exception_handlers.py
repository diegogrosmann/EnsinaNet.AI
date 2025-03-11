"""Handler de exceções customizado para a API.

Processa exceções de forma consistente, com suporte a logging
e formatação apropriada das mensagens de erro.
"""

import logging
import uuid
from typing import Optional, Any, Dict

from rest_framework.views import exception_handler
from rest_framework.exceptions import AuthenticationFailed, APIException
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Optional[Response]:
    """Processa exceções da API de forma padronizada.
    
    Args:
        exc: Exceção capturada.
        context: Contexto da requisição.
        
    Returns:
        Response formatada ou None se não puder ser processada.
    """
    error_id = str(uuid.uuid4())
    logger.error(f"Error ID {error_id}: {str(exc)}", exc_info=True)

    # Usa handler padrão do DRF primeiro
    response = exception_handler(exc, context)
    
    error_detail = _get_error_detail(exc, error_id)
    debug_info = {"error_id": error_id} if settings.DEBUG else {}

    if response is not None:
        response.data = {
            'error': error_detail,
            **debug_info
        }
    else:
        response = Response(
            {
                'error': error_detail if settings.DEBUG else "Erro interno do servidor",
                **debug_info
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    logger.debug(f"Resposta de erro preparada: {response.data}")
    return response

def _get_error_detail(exc: Exception, error_id: str) -> str:
    """Determina a mensagem de erro apropriada.
    
    Args:
        exc: Exceção a ser processada.
        error_id: Identificador único do erro.
        
    Returns:
        str: Mensagem de erro formatada.
    """
    if isinstance(exc, ApplicationError):
        return str(exc)
    elif isinstance(exc, AuthenticationFailed):
        return "Credenciais de autenticação inválidas ou não fornecidas"
    elif isinstance(exc, APIException):
        return str(exc.detail)
    elif settings.DEBUG:
        return f"{str(exc)} (Error ID: {error_id})"
    return "Erro interno do servidor. Por favor, tente novamente mais tarde."
