class APIClientError(Exception):
    """Erro genérico do APIClient."""
    pass

class FileProcessingError(APIClientError):
    """Erro ao processar arquivos."""
    pass

class APICommunicationError(APIClientError):
    """Erro na comunicação com a API externa."""
    pass

class MissingAPIKeyError(APIClientError):
    """Erro quando a chave de API não está configurada."""
    pass
