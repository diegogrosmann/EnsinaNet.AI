"""Handler de exceções customizado para a API.

Processa exceções de forma consistente, com suporte a logging
e formatação apropriada das mensagens de erro, garantindo que
todas as exceções sejam tratadas de maneira uniforme nas respostas
da API.
"""

import logging
import uuid
import traceback
from typing import Optional, Any, Dict, List

from rest_framework.views import exception_handler
from rest_framework.exceptions import AuthenticationFailed, APIException, ValidationError
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.db import IntegrityError, DatabaseError

from core.exceptions import ApplicationError, APIError, APIClientError, FileProcessingError
from core.types.api_response import APIResponse

logger = logging.getLogger(__name__)

def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> Optional[Response]:
    """Handler customizado para exceções da API.
    
    Processa todas as exceções lançadas durante o processamento de uma
    requisição à API, gerando respostas consistentes e registros de log
    detalhados para debug.
    
    Args:
        exc: Exceção lançada.
        context: Contexto da requisição onde a exceção ocorreu.
        
    Returns:
        Response com detalhes formatados do erro ou None para usar o
        handler padrão do DRF.
    """
    # Gera ID único para o erro para facilitar o rastreamento
    error_id = str(uuid.uuid4())[:8]
    
    # Log do erro com o ID
    logger.error(f"Error ID: {error_id} - {exc.__class__.__name__}", exc_info=exc)
    
    # Obtém detalhes da requisição para contexto
    request = context.get('request')
    view = context.get('view')
    view_name = view.__class__.__name__ if view else 'Unknown'
    
    # Log de informações adicionais para debug
    if request:
        logger.debug(f"Error {error_id} ocorreu em requisição {request.method} para {request.path}")
        logger.debug(f"View: {view_name}")
    
    # Obtém detalhes do erro
    error_detail, status_code = _get_error_detail_and_status(exc, error_id)
    
    # Prepara dados de contexto para log detalhado
    context_info = _prepare_context_info(context, exc)
    if context_info:
        logger.debug(f"Error {error_id} contexto: {context_info}")
    
    # Retorna resposta formatada usando o novo tipo APIResponse
    api_response = APIResponse(
        success=False,
        error=error_detail
    )
    
    # Adiciona ID do erro e detalhes técnicos em modo debug como metadados
    response_data = api_response.to_dict()
    if settings.DEBUG:
        response_data['error_id'] = error_id
        response_data['error_type'] = exc.__class__.__name__
        
    return Response(
        response_data,
        status=status_code
    )

def _get_error_detail_and_status(exc: Exception, error_id: str) -> tuple:
    """Determina a mensagem de erro apropriada e o status HTTP.
    
    Args:
        exc: Exceção a ser processada.
        error_id: Identificador único do erro.
        
    Returns:
        Tupla (mensagem_erro, status_code).
    """
    # Exceções da aplicação
    if isinstance(exc, APIClientError):
        return str(exc), exc.status_code
    elif isinstance(exc, APIError):
        return str(exc), exc.status_code
    elif isinstance(exc, ApplicationError):
        return str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR
        
    # Exceções do DRF
    elif isinstance(exc, ValidationError):
        # Formatar erros de validação de forma amigável
        if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
            errors = []
            for field, field_errors in exc.detail.items():
                field_error = f"{field}: {', '.join(str(e) for e in field_errors)}"
                errors.append(field_error)
            return '; '.join(errors), status.HTTP_400_BAD_REQUEST
        return str(exc), status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, AuthenticationFailed):
        return "Credenciais de autenticação inválidas ou não fornecidas", status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, APIException):
        return str(exc.detail), exc.status_code
        
    # Exceções do Django
    elif isinstance(exc, IntegrityError):
        return "Erro de integridade de dados", status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, DatabaseError):
        return "Erro de banco de dados", status.HTTP_500_INTERNAL_SERVER_ERROR
        
    # Outras exceções
    elif settings.DEBUG:
        return f"{str(exc)} (Error ID: {error_id})", status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Mensagem genérica para produção
    return "Erro interno do servidor. Por favor, tente novamente mais tarde.", status.HTTP_500_INTERNAL_SERVER_ERROR

def _prepare_context_info(context: Dict[str, Any], exc: Exception) -> Dict[str, Any]:
    """Prepara informações de contexto para logging detalhado.
    
    Args:
        context: Contexto da requisição.
        exc: Exceção ocorrida.
        
    Returns:
        Dicionário com informações de contexto relevantes.
    """
    info = {}
    
    # Tenta extrair dados da requisição se disponíveis
    request = context.get('request')
    if request:
        info['method'] = request.method
        info['path'] = request.path
        info['user'] = str(request.user) if hasattr(request, 'user') else 'Anonymous'
        info['query_params'] = dict(request.query_params) if hasattr(request, 'query_params') else {}
    
    # Adiciona stack trace em modo debug
    if settings.DEBUG:
        info['traceback'] = traceback.format_exc()
    
    return info
