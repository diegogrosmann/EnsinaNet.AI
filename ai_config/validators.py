"""Validadores para dados de treinamento de IA.

Define esquemas e funções de validação para garantir a integridade
dos dados usados no treinamento de modelos de IA.
"""

import logging
import json
from typing import Any, Dict, List, Tuple
import jsonschema
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Schema para validação dos dados de treinamento
TRAINING_DATA_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["user_message", "response"],
        "properties": {
            "system_message": {"type": "string"},
            "user_message": {"type": "string", "minLength": 1},
            "response": {"type": "string", "minLength": 1},
            "metadata": {
                "type": "object",
                "additionalProperties": True
            }
        },
        "additionalProperties": False
    },
    "minItems": 1
}

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
            logger.error(f"Conteúdo do arquivo inválido: {error_message}")
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
