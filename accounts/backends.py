"""
Custom authentication backend using email as username.

Este módulo fornece um backend de autenticação que permite aos usuários fazer login
utilizando seu endereço de email como nome de usuário.
"""

import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

class EmailBackend(ModelBackend):
    """Backend de autenticação que permite login utilizando email.

    Autentica o usuário utilizando o campo de email em vez do username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Autentica um usuário com base no email e na senha.

        Args:
            request (HttpRequest): Objeto de requisição atual.
            username (str): Email do usuário (usado como username).
            password (str): Senha do usuário.
            **kwargs: Argumentos adicionais.

        Returns:
            User: Objeto do usuário autenticado ou None se a autenticação falhar.
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
            # Executa o hasher para uniformizar o tempo de resposta e dificultar ataques
            User().set_password(password)
            logger.warning(f"Tentativa de autenticação com email inexistente: {username}")
        except Exception as e:
            logger.error(f"Erro durante autenticação do usuário {username}: {str(e)}", exc_info=True)

        return None
