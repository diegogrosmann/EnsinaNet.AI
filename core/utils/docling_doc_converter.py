"""Conversor de documentos usando o docling.

Fornece funções para converter documentos PDF e Word para texto
usando o docling como biblioteca de processamento.
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Optional

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from core.exceptions import FileProcessingError, ApplicationError
from core.types.base import JSONDict

logger = logging.getLogger(__name__)

def _get_pipeline_options() -> PdfPipelineOptions:
    """Configura as opções do pipeline docling.
    
    Tenta obter configurações personalizadas do banco de dados ou
    usa valores padrão se não estiverem disponíveis.
    
    Returns:
        PdfPipelineOptions: Opções configuradas para o pipeline.
    """
    logger.debug("Configurando opções do pipeline docling")
    
    try:
        from ai_config.models import DoclingConfiguration
        db_config = DoclingConfiguration.objects.first()
        
        if db_config:
            logger.info("Usando configurações Docling do banco de dados")
            options = PdfPipelineOptions(
                format_option=PdfFormatOption(db_config.format_option),
                text_only=db_config.text_only,
                ignore_images=db_config.ignore_images,
                extract_tables=db_config.extract_tables
            )
            return options
    except ImportError:
        logger.debug("Módulo ai_config.models não disponível, usando configurações padrão")
    except Exception as e:
        logger.warning(f"Erro ao obter configurações Docling do banco de dados: {str(e)}")
    
    # Configurações padrão
    logger.info("Usando configurações Docling padrão")
    return PdfPipelineOptions(
        format_option=PdfFormatOption.TEXT_IN_READING_ORDER,
        text_only=True,
        ignore_images=True,
        extract_tables=False
    )

def _convert_file_to_text(input_path: Path, format: InputFormat) -> str:
    """Converte um arquivo para texto usando o docling.
    
    Args:
        input_path: Caminho para o arquivo a ser convertido.
        format: Formato do arquivo de entrada.
        
    Returns:
        str: Texto extraído do documento.
        
    Raises:
        FileProcessingError: Se houver erro na conversão.
    """
    logger.debug(f"Convertendo arquivo para texto: {input_path} (formato: {format})")
    
    try:
        # Configurar o conversor com as opções apropriadas
        options = _get_pipeline_options()
        converter = DocumentConverter(
            backend=PyPdfiumDocumentBackend(),
            pipeline_options=options
        )
        
        # Converter o documento
        result = converter.convert_document(input_path, format)
        logger.info(f"Documento convertido com sucesso: {input_path}")
        
        # Exportar como texto plano ou markdown
        return result.document.export_to_markdown()
    except Exception as e:
        logger.exception(f"Erro ao converter arquivo para texto: {str(e)}")
        raise FileProcessingError(f"Erro na conversão do documento: {str(e)}")

def _process_bytes_with_temp_file(file_bytes: bytes, extension: str, 
                                converter_func: callable) -> str:
    """Processa bytes usando arquivo temporário.
    
    Cria um arquivo temporário com os bytes fornecidos e o processa
    usando a função de conversão especificada.
    
    Args:
        file_bytes: Conteúdo do arquivo em bytes.
        extension: Extensão do arquivo (sem ponto).
        converter_func: Função que converte o arquivo para texto.
        
    Returns:
        str: Texto extraído do documento.
        
    Raises:
        FileProcessingError: Se ocorrer erro durante o processamento.
    """
    logger.debug(f"Processando bytes com arquivo temporário (.{extension})")
    
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temp_file:
        try:
            # Escrever os bytes no arquivo temporário
            temp_file.write(file_bytes)
            temp_file.flush()
            temp_path = temp_file.name
            
            # Converter o arquivo para texto
            return converter_func(temp_path)
        except Exception as e:
            logger.exception(f"Erro ao processar arquivo temporário: {str(e)}")
            raise FileProcessingError(f"Erro ao processar documento: {str(e)}")
        finally:
            # Garantir que o arquivo temporário seja removido
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

def convert_pdf_file_to_text(pdf_path: str) -> str:
    """Converte um arquivo PDF local para texto utilizando o docling.

    Args:
        pdf_path: Caminho para o arquivo PDF.

    Returns:
        str: Texto extraído do PDF.

    Raises:
        FileProcessingError: Se a conversão do PDF falhar.
    """
    logger.info(f"Iniciando conversão de arquivo PDF: {pdf_path}")
    input_path = Path(pdf_path)
    
    if not input_path.exists():
        error_msg = f"Arquivo PDF não encontrado: {pdf_path}"
        logger.error(error_msg)
        raise FileProcessingError(error_msg)
        
    return _convert_file_to_text(input_path, InputFormat.PDF)

def convert_pdf_bytes_to_text(pdf_bytes: bytes, filename: str) -> str:
    """Converte o conteúdo de um PDF (em bytes) para texto utilizando o docling.

    Args:
        pdf_bytes: Conteúdo do PDF em formato de bytes.
        filename: Nome original do arquivo (para logging).

    Returns:
        str: Texto extraído do PDF.

    Raises:
        FileProcessingError: Se a conversão do PDF falhar.
    """
    logger.info(f"Iniciando conversão de PDF em bytes: {filename} ({len(pdf_bytes)} bytes)")
    return _process_bytes_with_temp_file(pdf_bytes, "pdf", convert_pdf_file_to_text)

def convert_word_file_to_text(word_path: str) -> str:
    """Converte um arquivo Word (DOCX) para texto utilizando o docling.

    Args:
        word_path: Caminho para o arquivo Word.

    Returns:
        str: Texto extraído do Word.

    Raises:
        FileProcessingError: Se a conversão do Word falhar.
    """
    logger.info(f"Iniciando conversão de arquivo Word: {word_path}")
    input_path = Path(word_path)
    
    if not input_path.exists():
        error_msg = f"Arquivo Word não encontrado: {word_path}"
        logger.error(error_msg)
        raise FileProcessingError(error_msg)
        
    return _convert_file_to_text(input_path, InputFormat.DOCX)

def convert_word_bytes_to_text(word_bytes: bytes, filename: str) -> str:
    """Converte o conteúdo de um arquivo Word (em bytes) para texto utilizando o docling.

    Args:
        word_bytes: Conteúdo do arquivo Word em formato de bytes.
        filename: Nome original do arquivo (para logging).

    Returns:
        str: Texto extraído do Word.

    Raises:
        FileProcessingError: Se a conversão do Word falhar.
    """
    logger.info(f"Iniciando conversão de Word em bytes: {filename} ({len(word_bytes)} bytes)")
    return _process_bytes_with_temp_file(word_bytes, "docx", convert_word_file_to_text)
