from rest_framework.views import exception_handler
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import uuid
from core.exceptions import ApplicationError

def custom_exception_handler(exc, context):
    """
    Manipulador customizado de exceções para a API.

    Args:
        exc (Exception): A exceção ocorrida.
        context (dict): Contexto adicional da exceção.

    Returns:
        Response: Resposta HTTP formatada com a mensagem de erro em português.
    """
    # Chama o manipulador padrão do DRF para gerar uma resposta inicial
    response = exception_handler(exc, context)

    # Define uma mensagem genérica para erros internos (produção)
    generic_error_message = "Erro interno do servidor. Por favor, tente novamente mais tarde."
    # Gera um ID único para o erro, útil para debug
    error_id = str(uuid.uuid4())

    # Determina a mensagem de erro com base no tipo da exceção
    if isinstance(exc, ApplicationError):
        error_detail = str(exc)
    elif isinstance(exc, AuthenticationFailed):
        error_detail = "As credenciais de autenticação não foram fornecidas."
    else:
        error_detail = str(exc)

    # Em ambiente DEBUG, adiciona o error_id para rastreamento; caso contrário, não expõe detalhes técnicos
    debug_info = {"error_id": error_id} if settings.DEBUG else {}

    if response is not None:
        # Se a resposta já possui uma chave 'detail', utiliza seu conteúdo (para DEBUG) ou substitui pela mensagem genérica
        if 'detail' in response.data:
            detail = response.data.pop('detail')
            if settings.DEBUG:
                error_detail = f"{detail} (Error ID: {error_id})"
            else:
                error_detail = generic_error_message
        response.data = {'error': error_detail, **debug_info}
    else:
        # Caso não haja resposta, cria uma nova resposta com status 500
        data = {'error': error_detail if settings.DEBUG else generic_error_message, **debug_info}
        response = Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response
