from abc import ABC
import uuid
from typing import Dict, Any

# Definir JSONDict localmente para evitar a dependência circular
JSONDict = Dict[str, Any]

class AppException(Exception, ABC):
    """Exceção genérica para toda a aplicação."""
    message: str
    code: str = None
    error_id: str = None
    status_code: int = None
    additional_data: JSONDict = None
    default_message: str = "Erro na aplicação"
    
    def __init__(self, 
                 message: str = None, 
                 code: str = None, 
                 error_id: str = None, 
                 status_code: int = None, 
                 additional_data: JSONDict = None ):
        """
        Inicializa uma nova exceção da aplicação.
        
        Args:
            message (str): Mensagem descritiva do erro
            code (str): Código identificador do erro
            additional_data (dict): Detalhes adicionais sobre o erro
            status_code (int): Código de status HTTP associado ao erro
            error_id (str): ID único para rastreamento do erro
        """
        # Garante que message tenha valor padrão se for None
        if message is None:
            message = self.default_message
            
        # Inicializa Exception
        Exception.__init__(self, message)

        # Inicializa atributos da exceção
        self.message = message
        self.code = code
        self.error_id = error_id or str(uuid.uuid4())
        self.status_code = status_code or 500
        self.additional_data = additional_data or {}
    
    def __str__(self):
        """Retorna a representação em string da exceção."""
        if self.code:
            return f"{self.code}: {self.message}"
        return self.message



