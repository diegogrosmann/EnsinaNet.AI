"""
Módulo de validadores centralizados.

Este módulo contém funções para validação de dados em diferentes contextos da aplicação,
como requisições de API, arquivos de treinamento e outros formatos de dados.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Tuple, Union
from django.http import JsonResponse
from django.core.exceptions import ValidationError
import jsonschema
from dataclasses import dataclass

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

from core.exceptions import APIError  # Certifique-se de importar a exceção centralizada

def validate_compare_request(data: Any) -> None:
    """Valida estrutura de requisição de comparação.

    Args:
        data: Dados da requisição a serem validados.

    Raises:
        APIError: Se algum campo obrigatório estiver ausente ou incorreto.
    """
    if not isinstance(data, dict):
        raise APIError("Dados da requisição devem ser um objeto", status_code=400)
        
    if 'instructor' not in data:
        raise APIError("Campo 'instructor' é obrigatório", status_code=400)
        
    if 'students' not in data:
        raise APIError("Campo 'students' é obrigatório", status_code=400)
        
    if not isinstance(data['students'], dict) or not data['students']:
        raise APIError("Campo 'students' deve ser um objeto não vazio", status_code=400)


def validate_document_input(data: Optional[Dict]) -> None:
    """Valida os dados de entrada para extração de documentos.
    
    Args:
        data: Dicionário contendo os dados do documento.
        
    Raises:
        FileProcessingError: Se os dados forem inválidos.
    """
    from core.exceptions import FileProcessingError
    
    if not data:
        raise FileProcessingError("Dados do documento não fornecidos")
    
    if not isinstance(data, dict):
        raise FileProcessingError("Dados do documento devem ser um objeto")
        
    if not data.get('name'):
        raise FileProcessingError("Nome do arquivo é obrigatório")
        
    if not data.get('content'):
        raise FileProcessingError("Conteúdo do arquivo é obrigatório")

# -----------------------------------------------------------------------------
# Validadores para arquivos de treinamento
# -----------------------------------------------------------------------------

def validate_training_data(data: Any) -> Tuple[bool, str]:
    """Valida os dados de treinamento contra o schema.

    Args:
        data: Dados a serem validados.

    Returns:
        Tuple[bool, str]: (True, '') se válido, (False, mensagem_erro) caso contrário.
    """
    try:
        if isinstance(data, str):
            data = json.loads(data)
            
        jsonschema.validate(instance=data, schema=TRAINING_DATA_SCHEMA)
        logger.debug(f"Dados de treinamento válidos: {len(data)} exemplos")
        return True, ''
        
    except json.JSONDecodeError as e:
        logger.warning(f"Erro ao decodificar JSON: {e}")
        return False, f"JSON inválido: {str(e)}"
        
    except jsonschema.exceptions.ValidationError as e:
        logger.warning(f"Erro de validação do schema: {e.message}")
        return False, f"Formato inválido: {e.message}"
        
    except Exception as e:
        logger.error(f"Erro inesperado na validação: {e}")
        return False, f"Erro na validação: {str(e)}"

def validate_training_file_content(content: str) -> List[Dict[str, Any]]:
    """Valida e processa o conteúdo do arquivo de treinamento.

    Args:
        content: Conteúdo do arquivo em formato string.

    Returns:
        List[Dict]: Dados processados e validados.

    Raises:
        ValidationError: Se o conteúdo for inválido.
    """
    try:
        # Tenta fazer o parse do JSON
        data = json.loads(content)
        
        # Valida o formato dos dados
        is_valid, error_message = validate_training_data(data)
        if not is_valid:
            raise ValidationError(error_message)
            
        logger.info(f"Arquivo de treinamento validado: {len(data)} exemplos")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar arquivo JSON: {e}")
        raise ValidationError(f"Arquivo JSON inválido: {str(e)}")
        
    except ValidationError:
        raise
        
    except Exception as e:
        logger.exception(f"Erro ao processar arquivo: {e}")
        raise ValidationError(f"Erro ao processar arquivo: {str(e)}")

@dataclass
class ValidationResult:
    """Resultado de uma validação."""
    is_valid: bool
    error_message: Optional[str] = None
    data: Optional[Any] = None

def validate_training_file(file) -> ValidationResult:
    """Valida o formato do arquivo de treinamento."""
    try:
        content = file.read()
        file.seek(0)  # Reset file pointer
        data = json.loads(content)
        
        if not isinstance(data, list):
            return ValidationResult(False, "Dados inválidos: deve ser uma lista de exemplos")
        
        for idx, example in enumerate(data, 1):
            if not isinstance(example, dict):
                return ValidationResult(False, f"Exemplo #{idx}: deve ser um objeto")
            if "user_message" not in example:
                return ValidationResult(False, f"Exemplo #{idx}: campo 'user_message' é obrigatório")
            if "response" not in example:
                return ValidationResult(False, f"Exemplo #{idx}: campo 'response' é obrigatório")
                
        logger.debug(f"Arquivo de treinamento válido com {len(data)} exemplos")
        return ValidationResult(True, data=data)
    except json.JSONDecodeError as e:
        logger.warning(f"Arquivo de treinamento com JSON inválido: {str(e)}")
        return ValidationResult(False, f"Arquivo JSON inválido: {str(e)}")
    except Exception as e:
        logger.error(f"Erro ao validar arquivo de treinamento: {str(e)}")
        return ValidationResult(False, f"Erro ao validar arquivo: {str(e)}")

