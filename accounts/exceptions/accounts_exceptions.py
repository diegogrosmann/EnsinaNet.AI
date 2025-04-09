from abc import ABC
from myproject.exceptions import AppException

class BaseAccountsException(AppException, ABC):
    """Exceção base para o módulo de contas."""
    
    def __init__(self, message=None, account_id=None, user_id=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if account_id:
            additional_data['account_id'] = account_id
        if user_id:
            additional_data['user_id'] = user_id
            
        super().__init__(message=message, additional_data=additional_data, **kwargs)


class AccountsException(BaseAccountsException):
    """Exceção para erros genéricos no módulo de contas."""
    
    def __init__(self, message=None, account_id=None, error_details=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if account_id:
            additional_data['account_id'] = account_id
        if error_details:
            additional_data['error_details'] = error_details
        
        super().__init__(message=message, additional_data=additional_data, **kwargs)