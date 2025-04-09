from abc import ABC
from myproject.exceptions import AppException


class BaseAIConfigException(AppException, ABC):
    """Exceção base para o módulo de configuração de IA."""
    
    def __init__(self, message=None, model_id=None, config_source=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if model_id:
            additional_data['model_id'] = model_id
        if config_source:
            additional_data['config_source'] = config_source
            
        super().__init__(message=message, additional_data=additional_data, **kwargs)


class AIConfigException(BaseAIConfigException):
    """Exceção para erros genéricos na configuração de IA."""
    
    def __init__(self, message=None, config_key=None, config_value=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if config_key:
            additional_data['config_key'] = config_key
        if config_value:
            additional_data['config_value'] = config_value
            
        super().__init__(message=message, additional_data=additional_data, **kwargs)
