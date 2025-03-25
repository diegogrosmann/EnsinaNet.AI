"""Utilitário para extração de texto de documentos.

Fornece funcionalidades para extrair texto de documentos PDF e Word
usando o docling como backend de processamento.
"""

import base64
import logging
from typing import Dict
from core.exceptions import FileProcessingError, APIError
from core.validators import validate_document_input
from core.utils.docling_doc_converter import convert_pdf_bytes_to_text, convert_word_bytes_to_text
from core.types.validation import ValidationResult
from core.types.base import JSONDict

logger = logging.getLogger(__name__)

def _get_file_extension(filename: str) -> str:
    """Obtém a extensão do arquivo.
    
    Args:
        filename: Nome do arquivo.
        
    Returns:
        str: Extensão do arquivo em minúsculas.
    """
    logger.debug(f"Extraindo extensão do arquivo: {filename}")
    return filename.lower().split('.')[-1] if '.' in filename else ''

def extract_text(data: JSONDict) -> str:
    """Extrai texto de um documento codificado em base64.
    
    Esta função processa um documento fornecido como conteúdo base64,
    validando o formato de entrada e extraindo o texto conforme o tipo
    de arquivo (PDF ou DOCX).
    
    Args:
        data: Dicionário com nome do arquivo e conteúdo em base64.
        
    Returns:
        str: Texto extraído do documento.
        
    Raises:
        APIError: Se ocorrer um erro interno inesperado.
        FileProcessingError: Se ocorrer um erro ao processar o arquivo.
    """
    logger.info("Iniciando processo de extração de texto de documento")
    
    try:
        # Validar os dados de entrada
        validation_result: ValidationResult = validate_document_input(data)
        if not validation_result.is_valid:
            raise FileProcessingError(validation_result.error_message)
        
        # Obter extensão do arquivo
        filename = data['name']
        extension = _get_file_extension(filename)
        
        # Decodificar conteúdo base64
        try:
            file_bytes = base64.b64decode(data['content'])
        except Exception as e:
            logger.error(f"Erro ao decodificar conteúdo base64: {str(e)}")
            raise FileProcessingError(f"Conteúdo base64 inválido: {str(e)}")
        
        # Processar conforme o tipo de arquivo
        if extension == 'pdf':
            logger.info(f"Processando arquivo PDF: {filename}")
            return convert_pdf_bytes_to_text(file_bytes, filename)
        elif extension in ['docx', 'doc']:
            logger.info(f"Processando arquivo Word: {filename}")
            return convert_word_bytes_to_text(file_bytes, filename)
        else:
            raise FileProcessingError(f"Formato de arquivo não suportado: {extension}")
    
    except FileProcessingError:
        # Repassa a exceção já formatada
        raise
    except Exception as e:
        logger.exception(f"Erro inesperado ao extrair texto: {str(e)}")
        raise APIError(f"Erro ao processar documento: {str(e)}")
