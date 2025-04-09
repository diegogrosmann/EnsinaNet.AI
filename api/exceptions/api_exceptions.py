from abc import ABC
from rest_framework import status
from myproject.exceptions import AppException


class BaseAPIException(AppException, ABC):
    """Exceção base para a API."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = 'Erro interno do servidor.'
    
    def __init__(self, message=None, status_code=None, request_id=None, endpoint=None, **kwargs):
        # Simplificando a obtenção de additional_data
        additional_data = kwargs.pop('additional_data', {})
        
        if request_id:
            additional_data['request_id'] = request_id
        if endpoint:
            additional_data['endpoint'] = endpoint
        
        # Use o status_code da instância se não fornecido
        if status_code is None:
            status_code = self.status_code
            
        super().__init__(
            message=message or self.default_message,
            status_code=status_code,
            additional_data=additional_data,
            **kwargs
        )


class APIException(BaseAPIException):
    """Exceção para erros genéricos na API."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = 'Erro genérico na API.'
    
    def __init__(self, message=None, endpoint=None, request_data=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if endpoint:
            additional_data['endpoint'] = endpoint
        if request_data:
            additional_data['request_data'] = request_data
            
        super().__init__(message=message or self.default_message,
                        status_code=self.status_code,
                        additional_data=additional_data,
                        **kwargs)


class APIClientException(BaseAPIException):
    """Exceção para erros originados no cliente da API."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = 'Erro no cliente da API.'
    
    def __init__(self, message=None, client_info=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if client_info:
            additional_data['client_info'] = client_info
            
        super().__init__(message=message or self.default_message,
                        status_code=self.status_code,
                        additional_data=additional_data,
                        **kwargs)


class APICommunicationException(BaseAPIException):
    """Exceção para erros de comunicação com a API."""
    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = 'Erro de comunicação com a API.'
    
    def __init__(self, message=None, request_url=None, response_code=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if request_url:
            additional_data['request_url'] = request_url
        if response_code:
            additional_data['response_code'] = response_code
            
        super().__init__(message=message or self.default_message,
                        status_code=self.status_code,
                        additional_data=additional_data,
                        **kwargs)


class MissingAPIKeyException(BaseAPIException):
    """Exceção lançada quando a chave da API está faltando."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_message = "API key não fornecida."

    def __init__(self, message=None, key_name=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if key_name:
            additional_data['key_name'] = key_name
            
        super().__init__(message=message or self.default_message,
                        status_code=self.status_code,
                        additional_data=additional_data,
                        **kwargs)
