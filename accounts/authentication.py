from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions
from .models import UserToken

class CustomTokenAuthentication(TokenAuthentication):
    keyword = 'Token'

    def authenticate_credentials(self, key):
        try:
            token = UserToken.objects.get(key=key)
        except UserToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Token inválido.')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('Usuário inativo ou token inválido.')

        return (token.user, token)
