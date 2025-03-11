"""Custom authentication backend using email as username.

This module provides an authentication backend that allows users to log in
using their email address.
"""

import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailBackend(ModelBackend):
    """Authentication backend that allows login using email address.

    This backend authenticates a user by using the email field as the username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Autentica um usuário com base no email e na senha.
        
        Args:
            request: Objeto HttpRequest da requisição atual.
            username: String contendo o email do usuário (usado como username).
            password: String contendo a senha do usuário.
            **kwargs: Argumentos adicionais que podem ser utilizados.
        
        Returns:
            User: Objeto de usuário autenticado ou None se a autenticação falhar.
        """
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
            
        if not username or not password:
            logger.warning("Tentativa de autenticação sem credenciais completas")
            return None
            
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
            logger.debug(f"Usuário encontrado: {username}")
            
            if user.check_password(password) and self.user_can_authenticate(user):
                logger.info(f"Autenticação bem-sucedida para: {username}")
                return user
            else:
                logger.warning(f"Falha na autenticação para: {username}")
                
        except User.DoesNotExist:
            # Executa o hasher de senha padrão para reduzir diferenças de tempo
            # e dificultar ataques de temporização
            User().set_password(password)
            logger.warning(f"Tentativa de autenticação com email inexistente: {username}")
        except Exception as e:
            logger.error(f"Erro durante autenticação do usuário {username}: {str(e)}")
            
        return None
