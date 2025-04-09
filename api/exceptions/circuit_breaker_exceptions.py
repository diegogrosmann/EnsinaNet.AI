from api.exceptions import BaseAPIException
from rest_framework import status


class CircuitOpenException(BaseAPIException):
    """Exceção levantada quando o circuito está aberto."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Serviço indisponível: Circuit Breaker aberto."

    def __init__(self, message=None, service_name=None, retry_after=None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        if service_name:
            additional_data['service_name'] = service_name
        if retry_after:
            additional_data['retry_after'] = retry_after
            
        super().__init__(message=message or self.default_message, 
                        status_code=self.status_code,
                        additional_data=additional_data, 
                        **kwargs)
