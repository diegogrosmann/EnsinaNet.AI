"""Utilitário para extração de texto de documentos.

Fornece funcionalidades para extrair texto de documentos PDF e Word
usando o docling como backend de processamento.
"""

import base64
import logging
from typing import Dict
from core.exceptions import FileProcessingError
from core.validators import validate_document_input
from core.utils.docling_doc_converter import convert_pdf_bytes_to_text, convert_word_bytes_to_text

logger = logging.getLogger(__name__)

def _get_file_extension(filename: str) -> str:
    """Obtém a extensão do arquivo.
    
    Args:
        filename: Nome do arquivo.
        
    Returns:
        str: Extensão do arquivo em minúsculas.
    """
    return filename.lower().split('.')[-1] if '.' in filename else ''

def extract_text(data: Dict) -> str:
    """Extrai texto de um documento codificado em base64.
    
    Args:
        data: Dicionário com name e content (base64).
        
    Returns:
        str: Texto extraído do documento.
        
    Raises:
        FileProcessingError: Se houver erro no processamento.
    """
    try:
        # Valida a entrada
        validate_document_input(data)
        
        name = data['name']
        content = data['content']
        extension = _get_file_extension(name)
        
        logger.info(f"Iniciando extração de texto do arquivo: {name}")
        
        try:
            file_bytes = base64.b64decode(content)
        except Exception as e:
            logger.error(f"Erro ao decodificar base64: {e}")
            raise FileProcessingError(f"Conteúdo base64 inválido: {e}")
        
        if extension == 'pdf':
            text = convert_pdf_bytes_to_text(file_bytes, name)
        elif extension == 'docx':
            text = convert_word_bytes_to_text(file_bytes, name)
        else:
            logger.error(f"Extensão não suportada: {extension}")
            raise FileProcessingError(f"Formato de arquivo não suportado: {extension}")
        
        logger.info(f"Texto extraído com sucesso: {name} ({len(text)} caracteres)")
        return text
        
    except FileProcessingError:
        raise
    except Exception as e:
        logger.exception(f"Erro não esperado ao processar arquivo: {e}")
        raise FileProcessingError(f"Erro ao processar documento: {e}")
