from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions
from .models import UserToken

class CustomTokenAuthentication(TokenAuthentication):
    """Autenticação personalizada por token utilizando o modelo UserToken.

    Atributos:
        keyword (str): Palavra-chave para autorização ("Token").
    """
    keyword = 'Token'

    def authenticate_credentials(self, key):
        """Autentica as credenciais do token.
        
        Argumentos:
            key (str): Chave do token.
        
        Retorna:
            tuple: Uma tupla contendo (usuário, token).
        
        Levanta:
            AuthenticationFailed: Se o token for inválido ou se o usuário estiver inativo.
        """
        try:
            token = UserToken.objects.get(key=key)
        except UserToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token inválido.')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('Usuário inativo ou token inválido.')

        return (token.user, token)
