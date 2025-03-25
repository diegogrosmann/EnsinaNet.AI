"""
Exceções customizadas para o projeto.

Define a hierarquia de exceções específicas para cada aplicação,
permitindo um tratamento de erros mais granular e informativo.
"""

import logging
import traceback
from typing import Optional

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Exceção base para toda a aplicação.

    Esta classe fornece a base para todas as exceções específicas da aplicação,
    permitindo um tratamento unificado de erros e logging centralizado.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.message = message or "Erro na aplicação"
        # Registra o erro com ou sem traceback conforme o parâmetro
        if log_traceback:
            logger.error(f"ApplicationError: {self.message}\n{traceback.format_exc()}")
        else:
            logger.error(f"ApplicationError: {self.message}")
        super().__init__(self.message)


class AccountsError(ApplicationError):
    """Exceção para erros relacionados à gestão de contas de usuário.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro na gestão de contas"
        super().__init__(message or self.default_message, log_traceback)


class AccountsAuthenticationError(AccountsError):
    """Exceção para erros específicos de autenticação.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro de autenticação"
        super().__init__(message or self.default_message, log_traceback)


class APIError(ApplicationError):
    """Exceção base para operações da API.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        status_code (int): Código HTTP associado ao erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, status_code: int = 500, log_traceback: bool = False):
        self.status_code = status_code
        self.default_message = "Erro interno da API"
        if log_traceback:
            logger.error(f"APIError ({status_code}): {message or self.default_message}\n{traceback.format_exc()}")
        else:
            logger.error(f"APIError ({status_code}): {message or self.default_message}")
        super().__init__(message or self.default_message, False)  # Evita registro duplo do traceback


class APIClientError(APIError):
    """Exceção para erros relacionados aos clientes de API.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        status_code (int): Código HTTP associado ao erro (padrão 400).
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, status_code: int = 400, log_traceback: bool = False):
        self.default_message = "Erro no uso da API"
        super().__init__(message or self.default_message, status_code, log_traceback)


class APICommunicationError(APIClientError):
    """Exceção para erros de comunicação com APIs externas.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro de comunicação com serviço externo"
        super().__init__(message or self.default_message, status_code=503, log_traceback=log_traceback)


class FileProcessingError(APIClientError):
    """Exceção para erros no processamento de arquivos.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro no processamento do arquivo"
        super().__init__(message or self.default_message, status_code=400, log_traceback=log_traceback)


class MissingAPIKeyError(APIClientError):
    """Exceção para chave de API ausente.

    Args:
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, log_traceback: bool = False):
        self.default_message = "Chave de API não configurada"
        super().__init__(self.default_message, status_code=401, log_traceback=log_traceback)


class AIConfigError(ApplicationError):
    """Exceção para erros na configuração de IA.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro de configuração de IA"
        super().__init__(message or self.default_message, log_traceback)


class TrainingError(AIConfigError):
    """Exceção para erros durante o treinamento de modelos de IA.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro durante o processo de treinamento"
        super().__init__(message or self.default_message, log_traceback)


class PublicError(ApplicationError):
    """Exceção para erros que podem ser expostos diretamente ao usuário final.

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Erro na interface pública"
        super().__init__(message or self.default_message, log_traceback)


class CircuitOpenError(ApplicationError):
    """Exceção para indicar que o circuito está aberto (Circuit Breaker).

    Args:
        message (Optional[str]): Mensagem descritiva do erro.
        log_traceback (bool): Se True, registra o traceback completo no log.
    """
    def __init__(self, message: Optional[str] = None, log_traceback: bool = False):
        self.default_message = "Circuit breaker aberto para esta API"
        super().__init__(message or self.default_message, log_traceback)
