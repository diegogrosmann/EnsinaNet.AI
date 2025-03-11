import logging
from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions
from .models import UserToken

logger = logging.getLogger(__name__)

class CustomTokenAuthentication(TokenAuthentication):
    """Autenticação personalizada por token utilizando o modelo UserToken.
    
    Implementa autenticação de API com base em tokens.
    Estende a TokenAuthentication padrão do DRF para usar o modelo UserToken.
    
    Attributes:
        keyword: Palavra-chave para o cabeçalho de autorização (ex: "Token").
    """
    keyword = 'Token'

    def authenticate_credentials(self, key):
        """Autentica as credenciais do token fornecido.
        
        Args:
            key: String contendo a chave do token a ser verificada.
        
        Returns:
            tuple: Uma tupla contendo (usuário, token) se a autenticação for bem-sucedida.
        
        Raises:
            AuthenticationFailed: Se o token for inválido ou o usuário estiver inativo.
        """
        try:
            token = UserToken.objects.get(key=key)
            logger.info(f"Token '{token.name}' autenticado com sucesso para {token.user.email}")
        except UserToken.DoesNotExist:
            logger.warning(f"Tentativa de autenticação com token inválido: {key[:8]}...")
            raise exceptions.AuthenticationFailed('Token inválido.')
        except Exception as e:
            logger.error(f"Erro durante autenticação do token: {str(e)}")
            raise exceptions.AuthenticationFailed('Erro ao processar autenticação.')

        if not token.user.is_active:
            logger.warning(f"Tentativa de autenticação com usuário inativo: {token.user.email}")
            raise exceptions.AuthenticationFailed('Usuário inativo ou token inválido.')

        return (token.user, token)
