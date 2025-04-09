# Este arquivo torna o diretório 'exceptions' um pacote Python.
from .api_exceptions import BaseAPIException, APIClientException, APICommunicationException, MissingAPIKeyException
from .circuit_breaker_exceptions import CircuitOpenException
