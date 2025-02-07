"""Custom authentication backend using email as username.

This module provides an authentication backend that allows users to log in
using their email address.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """Authentication backend that allows login using email address.

    This backend authenticates a user by using the email field as the username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Autentica um usuário com base no email e na senha.
        
        Argumentos:
            request (HttpRequest): Objeto da requisição HTTP.
            username (str, opcional): Email do usuário.
            password (str, opcional): Senha do usuário.
            **kwargs: Argumentos adicionais.
        
        Retorna:
            User ou None: Usuário autenticado ou None se as credenciais forem inválidas.
        """
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing differences
            User().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
