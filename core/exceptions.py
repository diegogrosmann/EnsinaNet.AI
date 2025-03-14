"""Exceções customizadas para o projeto.

Define a hierarquia de exceções específicas para cada aplicação,
permitindo um tratamento de erros mais granular e informativo.
"""

class ApplicationError(Exception):
    """Exceção base para toda a aplicação."""
    pass

class AccountsError(ApplicationError):
    """Exceções relacionadas à gestão de contas de usuário."""
    pass

class AccountsAuthenticationError(AccountsError):
    """Exceções específicas de autenticação."""
    pass

class APIError(ApplicationError):
    """Exceções base para operações da API."""
    def __init__(self, message: str = None, status_code: int = 500):
        self.status_code = status_code
        super().__init__(message or "Erro interno da API")

class APIClientError(APIError):
    """Exceções relacionadas aos clientes de API."""
    pass

class APICommunicationError(APIClientError):
    """Exceções de comunicação com APIs externas."""
    def __init__(self, message: str = None):
        super().__init__(
            message or "Erro de comunicação com serviço externo",
            status_code=503
        )

class FileProcessingError(APIClientError):
    """Exceções no processamento de arquivos."""
    def __init__(self, message: str = None):
        super().__init__(
            message or "Erro no processamento do arquivo",
            status_code=400
        )

class MissingAPIKeyError(APIClientError):
    """Exceções para chaves de API ausentes."""
    def __init__(self):
        super().__init__(
            "Chave de API não configurada",
            status_code=401
        )

class AIConfigError(ApplicationError):
    """Exceções base para configuração de IA."""
    pass

class TrainingError(AIConfigError):
    """Exceções específicas de treinamento."""
    def __init__(self, message: str = None):
        super().__init__(
            message or "Erro durante o processo de treinamento"
        )

class PublicError(ApplicationError):
    """Exceções para a interface pública."""
    pass

class CircuitOpenError(ApplicationError):
    """Erro lançado quando o circuito está aberto."""
    def __init__(self, message: str = None):
        super().__init__(message or "Circuit breaker aberto para esta API")