from rest_framework.views import exception_handler
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    """Manipulador customizado de exceções para a API.

    Args:
        exc (Exception): A exceção ocorrida.
        context (dict): Contexto adicional da exceção.

    Returns:
        Response: Resposta HTTP formatada com a mensagem de erro em português.
    """
    # Chama o manipulador de exceções padrão para obter a resposta inicial
    response = exception_handler(exc, context)
    
    if response is not None:
        # Verifica se a chave 'detail' está presente na resposta
        if 'detail' in response.data:
            # Move o conteúdo de 'detail' para 'error'
            response.data['error'] = response.data.pop('detail')
        elif isinstance(exc, AuthenticationFailed):
            # Exemplo: caso específico para AuthenticationFailed
            response.data = {'error': 'As credenciais de autenticação não foram fornecidas.'}
        # Você pode adicionar outras customizações aqui se necessário

    return response
