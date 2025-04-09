from myproject.exceptions import AppException

class BaseClientVersionException(AppException):
    pass

class ClientVersionException(BaseClientVersionException):
    pass