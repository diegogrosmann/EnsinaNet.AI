from myproject.exceptions import AppException


class BasePublicException(AppException):
    """Exceção base para o módulo público."""
    pass


class PublicException(BasePublicException):
    """Exceção para erros genéricos no módulo público."""
    pass

