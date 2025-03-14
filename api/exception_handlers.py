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
    """Handler customizado para exceções da API."""
    # Gera ID único para o erro
    error_id = str(uuid.uuid4())
    
    # Log do erro com o ID
    logger.error(f"Error ID: {error_id}", exc_info=exc)
    
    # Obtém detalhes do erro
    error_detail = _get_error_detail(exc, error_id)
    
    # Retorna resposta formatada
    return Response(
        {
            'success': False,
            'error': error_detail,
            'error_id': error_id
        },
        status=getattr(exc, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
    )

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
