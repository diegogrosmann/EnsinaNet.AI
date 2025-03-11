# core/exceptions.py

class ApplicationError(Exception):
    """
    Exceção base para toda a aplicação.
    """
    pass

# Exceções para a app Accounts
class AccountsError(ApplicationError):
    """
    Exceção base para a app Accounts.
    """
    pass

class AccountsAuthenticationError(AccountsError):
    """
    Exceção para erros de autenticação na app Accounts.
    """
    pass

# Exceções para a app API
class APIError(ApplicationError):
    """
    Exceção base para a app API.
    """
    pass

class APIClientError(APIError):
    """
    Exceção genérica para erros em clientes de API.
    """
    pass

class FileProcessingError(APIClientError):
    """
    Exceção para erros no processamento de arquivos.
    """
    pass

class APICommunicationError(APIClientError):
    """
    Exceção para erros de comunicação com APIs externas.
    """
    pass

class MissingAPIKeyError(APIClientError):
    """
    Exceção para erro quando a chave de API não está configurada.
    """
    pass

# Exceções para a app AI Config (configuração de IA)
class AIConfigError(ApplicationError):
    """
    Exceção base para a app de Configuração de IA.
    """
    pass

class TrainingError(AIConfigError):
    """
    Exceção para erros durante processos de treinamento.
    """
    pass

# Exceções para a app Public
class PublicError(ApplicationError):
    """
    Exceção base para a app Public.
    """
    pass
