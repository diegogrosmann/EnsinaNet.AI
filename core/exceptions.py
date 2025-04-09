from abc import ABC
from myproject.exceptions import AppException

class BaseCoreException(AppException, ABC):
    """Exceção base para o módulo core."""
    default_message = "Erro no módulo core."
    pass


class CoreException(BaseCoreException):
    """Exceção para erros genéricos no módulo core."""
    default_message = "Erro genérico no módulo core."
    pass


class FileProcessingException(BaseCoreException):
    """Exceção para erros no processamento de arquivos.
    
    Args:
        message: Mensagem descrevendo o erro
        filepath: Caminho do arquivo que gerou o erro (opcional)
        details: Detalhes adicionais sobre o erro (opcional)
        additional_data: Dados adicionais relacionados ao erro (opcional)
    """
    default_message = "Erro ao processar o arquivo."
    def __init__(self, message: str = None, filepath: str = None, details: dict = None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        
        self.filepath = filepath
        self.details = details or {}
        
        if filepath:
            additional_data['filepath'] = filepath
        if details:
            additional_data['details'] = details
            
        detailed_msg = message or self.default_message
        if filepath:
            detailed_msg = f"{detailed_msg} (arquivo: {filepath})"
            
        super().__init__(message=detailed_msg, additional_data=additional_data, **kwargs)


class CoreValidationException(BaseCoreException):
    """Exceção base para erros de validação.
    
    Esta classe serve como base para erros relacionados à validação de dados,
    como tipos inválidos ou valores fora dos limites esperados.
    
    Args:
        message: Mensagem descrevendo o erro de validação
        field: Campo que falhou na validação (opcional)
        type_name: Nome do tipo que teve validação falha (opcional)
        additional_data: Dados adicionais relacionados ao erro (opcional)
    """
    default_message = "Erro de validação."
    def __init__(self, message: str = None, field: str = None, type_name: str = None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        
        self.field = field
        self.type_name = type_name
        
        if field:
            additional_data['field'] = field
        if type_name:
            additional_data['type_name'] = type_name
        
        detailed_msg = message or self.default_message
        
        if type_name:
            detailed_msg = f"[{type_name}] {detailed_msg}"
        if field:
            detailed_msg = f"{detailed_msg} (campo: {field})"
            
        super().__init__(message=detailed_msg, additional_data=additional_data, **kwargs)


class CoreValueException(CoreValidationException, ValueError):
    """Exceção para valores inválidos em tipos personalizados.
    
    Usada quando um objeto de dados viola suas regras de validação.
    Estende ValueError para manter compatibilidade com código existente.
    
    Args:
        message: Mensagem descrevendo a violação.
        field: Campo que contém o valor inválido (opcional).
        type_name: Nome do tipo que teve validação falha (opcional).
        additional_data: Dados adicionais relacionados ao erro (opcional)
    """
    default_message = "Valor inválido."
    def __init__(self, message: str = None, field: str = None, type_name: str = None, **kwargs):
        super().__init__(message=message or self.default_message, field=field, type_name=type_name, **kwargs)
        ValueError.__init__(self, str(self))


class CoreTypeException(CoreValidationException, TypeError):
    """Exceção para erros de tipo inválido.
    
    Usada quando um valor tem um tipo incompatível com o esperado.
    Estende TypeError para manter compatibilidade com código existente.
    
    Args:
        message: Mensagem descrevendo o erro de tipo.
        expected_type: Tipo que era esperado (opcional).
        received_type: Tipo que foi recebido (opcional).
        field: Campo que contém o tipo inválido (opcional).
        type_name: Nome do tipo que teve validação falha (opcional).
        additional_data: Dados adicionais relacionados ao erro (opcional)
    """
    default_message = "Tipo inválido."
    def __init__(self, message: str = None, expected_type: str = None, received_type: str = None, 
                field: str = None, type_name: str = None, **kwargs):
        additional_data = kwargs.pop('additional_data', {})
        
        self.expected_type = expected_type
        self.received_type = received_type
        
        if expected_type:
            additional_data['expected_type'] = expected_type
        if received_type:
            additional_data['received_type'] = received_type
        
        detailed_msg = message or self.default_message
        
        if expected_type and received_type:
            detailed_msg = f"{detailed_msg} (esperado: {expected_type}, recebido: {received_type})"
        elif expected_type:
            detailed_msg = f"{detailed_msg} (esperado: {expected_type})"
            
        super().__init__(message=detailed_msg, field=field, type_name=type_name, additional_data=additional_data, **kwargs)
        TypeError.__init__(self, str(self))