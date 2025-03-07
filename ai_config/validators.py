import json
from typing import Any, Dict, List
import jsonschema

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
            "metadata": {"type": "object"}
        }
    },
    "minItems": 1
}

def validate_training_data(data: Any) -> bool:
    """
    Valida os dados de treinamento contra o schema.

    Args:
        data: Dados a serem validados

    Returns:
        bool: True se válido, False caso contrário
    """
    try:
        if isinstance(data, str):
            data = json.loads(data)
        
        jsonschema.validate(instance=data, schema=TRAINING_DATA_SCHEMA)
        return True
        
    except (json.JSONDecodeError, jsonschema.exceptions.ValidationError) as e:
        return False

def validate_training_file_content(content: str) -> List[Dict[str, Any]]:
    """
    Valida e processa o conteúdo do arquivo de treinamento.

    Args:
        content: Conteúdo do arquivo

    Returns:
        List[Dict]: Dados processados e validados

    Raises:
        ValidationError: Se o conteúdo for inválido
    """
    try:
        data = json.loads(content)
        if not validate_training_data(data):
            raise ValueError("Formato de dados inválido")
        return data
    except Exception as e:
        raise ValueError(f"Erro ao processar arquivo: {str(e)}")
