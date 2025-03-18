"""
Módulo de validadores centralizados.

Este módulo contém funções para validação de dados em diferentes contextos da aplicação,
como requisições de API, arquivos de treinamento e outros formatos de dados.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from django.core.exceptions import ValidationError
import jsonschema

from core.types.validation import ValidationResult

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Schemas para validação
# -----------------------------------------------------------------------------

TRAINING_DATA_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["user_message", "response"],
        "properties": {
            "user_message": {"type": "string"},
            "system_message": {"type": "string"},
            "response": {"type": "string"}
        },
        "additionalProperties": False
    },
    "minItems": 1
}



# -----------------------------------------------------------------------------
# Validadores para API
# -----------------------------------------------------------------------------

from core.exceptions import APIError

def validate_compare_request(data: Any) -> ValidationResult:
    """Valida estrutura de requisição de comparação.

    Args:
        data: Dados da requisição a serem validados.

    Returns:
        ValidationResult: Resultado da validação contendo status e dados processados.
    """
    if not isinstance(data, dict):
        return ValidationResult(False, error_message="Dados da requisição devem ser um objeto")
        
    if 'instructor' not in data:
        return ValidationResult(False, error_message="Campo 'instructor' é obrigatório")
        
    if 'students' not in data:
        return ValidationResult(False, error_message="Campo 'students' é obrigatório")
        
    if not isinstance(data['students'], dict) or not data['students']:
        return ValidationResult(False, error_message="Campo 'students' deve ser um objeto não vazio")
        
    return ValidationResult(True, data=data)


def validate_document_input(data: Optional[Dict]) -> ValidationResult:
    """Valida os dados de entrada para extração de documentos.
    
    Args:
        data: Dicionário contendo os dados do documento.
        
    Returns:
        ValidationResult: Resultado da validação contendo status e dados processados.
    """
    if not data:
        return ValidationResult(False, error_message="Dados do documento não fornecidos")
    
    if not isinstance(data, dict):
        return ValidationResult(False, error_message="Dados do documento devem ser um objeto")
        
    if not data.get('name'):
        return ValidationResult(False, error_message="Nome do arquivo é obrigatório")
        
    if not data.get('content'):
        return ValidationResult(False, error_message="Conteúdo do arquivo é obrigatório")
        
    return ValidationResult(True, data=data)

# -----------------------------------------------------------------------------
# Validadores para arquivos de treinamento
# -----------------------------------------------------------------------------
def validate_training_data(data: Any, as_exception: bool = False) -> ValidationResult:
    """Valida os dados de treinamento contra o schema.

    Args:
        data: Dados a serem validados.
        as_exception: Se True, lança ValidationError em vez de retornar ValidationResult.

    Returns:
        ValidationResult: Resultado da validação contendo status e dados processados.
        
    Raises:
        ValidationError: Se as_exception=True e os dados forem inválidos.
    """
    try:
        if isinstance(data, str):
            data = json.loads(data)
            
        jsonschema.validate(instance=data, schema=TRAINING_DATA_SCHEMA)
        logger.debug(f"Dados de treinamento válidos: {len(data)} exemplos")
        return ValidationResult(True, data=data)
        
    except json.JSONDecodeError as e:
        error_msg = f"JSON inválido: {str(e)}"
        logger.warning(f"Erro ao decodificar JSON: {e}")
    except jsonschema.exceptions.ValidationError as e:
        error_msg = f"Formato inválido: {e.message}"
        logger.warning(f"Erro de validação do schema: {e.message}")
    except Exception as e:
        error_msg = f"Erro na validação: {str(e)}"
        logger.error(f"Erro inesperado na validação: {e}")
    
    if as_exception:
        raise ValidationError(error_msg)
    return ValidationResult(False, error_message=error_msg)

def validate_training_file(file) -> ValidationResult:
    """Valida o formato do arquivo de treinamento.
    
    Args:
        file: Objeto de arquivo para validação.
        
    Returns:
        ValidationResult: Resultado da validação.
    """
    try:
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        file.seek(0)  # Reset file pointer
        
        # Usa a função unificada de validação
        return validate_training_data(content)
    except Exception as e:
        logger.error(f"Erro ao validar arquivo de treinamento: {str(e)}")
        return ValidationResult(False, error_message=f"Erro ao validar arquivo: {str(e)}")


