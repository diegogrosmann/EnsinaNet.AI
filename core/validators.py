"""
Módulo de validadores centralizados.

Este módulo contém funções para validação de dados em diferentes contextos da aplicação,
como requisições de API, arquivos de treinamento e outros formatos de dados.
"""

import logging
import json
from typing import Any, Dict, Optional
from django.core.exceptions import ValidationError
import jsonschema

from core.types.validation import ValidationResult
from core.types.base import JSONDict
from core.exceptions import APIError, FileProcessingError, APIClientError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Schema para validação dos dados de treinamento
# -----------------------------------------------------------------------------
TRAINING_DATA_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["user_message", "response"],
        "properties": {
            "system_message": {"type": "string"},
            "user_message": {"type": "string"},
            "response": {"type": "string"}
        },
        "additionalProperties": False
    },
    "minItems": 1
}


def validate_compare_request(data: Any) -> ValidationResult:
    """Valida a estrutura da requisição de comparação.

    Verifica se a requisição de comparação contém todos os campos obrigatórios e se estão no formato correto.

    Args:
        data: Dados da requisição a serem validados.

    Returns:
        ValidationResult: Resultado da validação com flag de sucesso/erro e mensagem.

    Raises:
        APIClientError: Caso ocorra um erro inesperado durante a validação.
    """
    logger.debug("Iniciando validação da requisição de comparação")
    try:
        # Verificar presença e tipo dos campos obrigatórios
        if not isinstance(data, dict):
            return ValidationResult(False, error_message="Dados de comparação devem ser um objeto")
        
        if 'instructor' not in data:
            return ValidationResult(False, error_message="Campo 'instructor' é obrigatório")
            
        if 'students' not in data:
            return ValidationResult(False, error_message="Campo 'students' é obrigatório")
            
        if not isinstance(data['students'], dict):
            return ValidationResult(False, error_message="Campo 'students' deve ser um objeto")
            
        if len(data['students']) == 0:
            return ValidationResult(False, error_message="Pelo menos um estudante deve ser fornecido")
        
        # Validação bem-sucedida
        return ValidationResult(True, data=data)
    except Exception as e:
        logger.exception(f"Erro ao validar requisição de comparação: {str(e)}")
        raise APIClientError(f"Erro ao validar requisição: {str(e)}")

def validate_document_input(data: Optional[Dict]) -> ValidationResult:
    """Valida os dados de entrada de um documento.

    Verifica se os dados fornecidos contêm os campos obrigatórios 'name' e 'content'
    e se estão no formato correto.

    Args:
        data: Dicionário com dados do documento a ser validado.

    Returns:
        ValidationResult: Resultado da validação com flag de sucesso/erro e mensagem.

    Raises:
        APIClientError: Caso ocorra um erro inesperado durante a validação.
    """
    logger.debug("Iniciando validação dos dados de entrada do documento")
    try:
        # Verificar se data existe
        if data is None:
            return ValidationResult(False, error_message="Nenhum dado fornecido")
        
        # Verificar campos obrigatórios
        if 'name' not in data:
            return ValidationResult(False, error_message="Campo 'name' é obrigatório")
        
        if 'content' not in data:
            return ValidationResult(False, error_message="Campo 'content' é obrigatório")
        
        # Verificar se content é uma string de base64 válida
        if not isinstance(data['content'], str) or not data['content']:
            return ValidationResult(False, error_message="Campo 'content' deve ser uma string não vazia")
        
        # Validação bem-sucedida
        return ValidationResult(True, data=data)
    except Exception as e:
        logger.exception(f"Erro ao validar dados do documento: {str(e)}")
        raise APIClientError(f"Erro ao validar documento: {str(e)}")

def validate_training_data(data: Any, as_exception: bool = False) -> ValidationResult:
    """Valida os dados de treinamento contra o schema predefinido.

    Converte a string JSON para objeto (se necessário) e valida os dados de treinamento utilizando o schema definido.

    Args:
        data: Dados a serem validados, pode ser string JSON ou objeto já decodificado.
        as_exception: Se True, levanta exceção em caso de erro em vez de retornar ValidationResult.

    Returns:
        ValidationResult: Resultado da validação com flag de sucesso/erro e mensagem.

    Raises:
        FileProcessingError: Se ocorrer um erro inesperado durante a validação ou se as_exception=True.
    """
    logger.debug("Iniciando validação dos dados de treinamento")
    try:
        # Converter para objeto se for string
        json_data = data
        if isinstance(data, str):
            json_data = json.loads(data)
        
        # Validar contra o schema
        jsonschema.validate(instance=json_data, schema=TRAINING_DATA_SCHEMA)
        
        # Validação adicional para garantir que cada item tem os campos necessários
        for index, item in enumerate(json_data):
            if 'user_message' not in item or not item['user_message']:
                error_msg = f"Item {index}: Campo 'user_message' é obrigatório e não pode estar vazio"
                if as_exception:
                    raise ValidationError(error_msg)
                return ValidationResult(False, error_message=error_msg)
                
            if 'response' not in item or not item['response']:
                error_msg = f"Item {index}: Campo 'response' é obrigatório e não pode estar vazio"
                if as_exception:
                    raise ValidationError(error_msg)
                return ValidationResult(False, error_message=error_msg)
        
        # Validação bem-sucedida
        return ValidationResult(True, data=json_data)
    except ValidationError as e:
        error_msg = f"Dados de treinamento inválidos: {str(e)}"
        if as_exception:
            raise FileProcessingError(error_msg)
        return ValidationResult(False, error_message=error_msg)
    except json.JSONDecodeError as e:
        error_msg = f"JSON inválido: {str(e)}"
        if as_exception:
            raise FileProcessingError(error_msg)
        return ValidationResult(False, error_message=error_msg)
    except Exception as e:
        logger.exception(f"Erro ao validar dados de treinamento: {str(e)}")
        error_msg = f"Erro ao validar dados de treinamento: {str(e)}"
        if as_exception:
            raise FileProcessingError(error_msg)
        return ValidationResult(False, error_message=error_msg)

def validate_training_file(file) -> ValidationResult:
    """Valida o arquivo de treinamento fornecido.

    Lê o conteúdo do arquivo, converte de bytes para string se necessário e valida o conteúdo
    utilizando a função de validação dos dados de treinamento.

    Args:
        file: Objeto de arquivo a ser validado.

    Returns:
        ValidationResult: Resultado da validação com flag de sucesso/erro e mensagem.

    Raises:
        FileProcessingError: Se ocorrer um erro inesperado durante a validação do arquivo.
    """
    logger.debug("Iniciando validação do arquivo de treinamento")
    try:
        file.seek(0)
        content = file.read()
        
        # Converter bytes para string se necessário
        if isinstance(content, bytes):
            content = content.decode('utf-8')
            
        return validate_training_data(content)
    except UnicodeDecodeError as e:
        error_message = f"Arquivo não está em formato UTF-8 válido: {str(e)}"
        return ValidationResult(False, error_message=error_message)
    except Exception as e:
        logger.exception(f"Erro ao validar arquivo de treinamento: {str(e)}")
        raise FileProcessingError(f"Erro ao validar arquivo: {str(e)}")
