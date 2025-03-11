"""Conversor de documentos usando o docling.

Fornece funções para converter documentos PDF e Word para texto
usando o docling como biblioteca de processamento.
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

logger = logging.getLogger(__name__)

def _get_pipeline_options() -> PdfPipelineOptions:
    """Configura as opções do pipeline docling.
    
    Returns:
        PdfPipelineOptions: Opções configuradas para o pipeline.
    """
    try:
        from ai_config.models import DoclingConfiguration
    except ImportError:
        logger.warning("DoclingConfiguration não disponível")
        return PdfPipelineOptions()

    try:
        config = DoclingConfiguration.objects.first()
        if not config:
            logger.debug("Nenhuma configuração Docling encontrada, usando padrões")
            return PdfPipelineOptions()

        options = PdfPipelineOptions()
        options.do_ocr = config.do_ocr
        options.do_table_structure = config.do_table_structure
        options.table_structure_options.do_cell_matching = config.do_cell_matching
        
        if hasattr(options, 'accelerator_options'):
            options.accelerator_options.device = config.accelerator_device
            
        if config.custom_options:
            for key, value in config.custom_options.items():
                if hasattr(options, key):
                    setattr(options, key, value)
                else:
                    logger.warning(f"Opção desconhecida ignorada: {key}")
        
        logger.debug(f"Opções Docling configuradas: OCR={options.do_ocr}, "
                    f"Table={options.do_table_structure}")
        return options
        
    except Exception as e:
        logger.error(f"Erro ao configurar opções Docling: {e}")
        return PdfPipelineOptions()

def _convert_file_to_text(input_path: Path, format: InputFormat) -> str:
    """Converte um arquivo para texto usando o docling.
    
    Args:
        input_path: Caminho do arquivo.
        format: Formato do arquivo (PDF/DOCX).
        
    Returns:
        str: Texto extraído do documento.
        
    Raises:
        Exception: Se houver erro na conversão.
    """
    options = _get_pipeline_options()
    
    converter = DocumentConverter(
        allowed_formats=[format],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=options,
                backend=PyPdfiumDocumentBackend
            )
        }
    )
    
    result = converter.convert(input_path)
    if not result:
        raise Exception("Falha na conversão do documento")
        
    return result.document.export_to_markdown()

def _process_bytes_with_temp_file(file_bytes: bytes, extension: str, 
                                converter_func: callable) -> str:
    """Processa bytes usando arquivo temporário.
    
    Args:
        file_bytes: Conteúdo do arquivo.
        extension: Extensão do arquivo.
        converter_func: Função de conversão a ser usada.
        
    Returns:
        str: Texto extraído do documento.
    """
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as temp_file:
        try:
            temp_file.write(file_bytes)
            temp_file.flush()
            return converter_func(temp_file.name)
        finally:
            os.unlink(temp_file.name)

def convert_pdf_file_to_text(pdf_path: str) -> str:
    """Converte um arquivo PDF local para texto utilizando o docling.

    Args:
        pdf_path (str): Caminho para o arquivo PDF.

    Returns:
        str: Texto convertido em formato markdown.

    Raises:
        Exception: Se a conversão do PDF falhar.
    """
    input_path = Path(pdf_path)
    return _convert_file_to_text(input_path, InputFormat.PDF)

def convert_pdf_bytes_to_text(pdf_bytes: bytes, filename: str) -> str:
    """Converte o conteúdo de um PDF (em bytes) para texto utilizando o docling.

    Args:
        pdf_bytes (bytes): Conteúdo do PDF.
        filename (str): Nome do arquivo, utilizado para identificação.

    Returns:
        str: Texto convertido em formato markdown.

    Raises:
        Exception: Se a conversão do PDF falhar.
    """
    return _process_bytes_with_temp_file(pdf_bytes, "pdf", convert_pdf_file_to_text)

def convert_word_file_to_text(word_path: str) -> str:
    """Converte um arquivo Word (DOCX) para texto utilizando o docling.

    Args:
        word_path (str): Caminho para o arquivo Word.

    Returns:
        str: Texto convertido em formato markdown.

    Raises:
        Exception: Se a conversão do Word falhar.
    """
    input_path = Path(word_path)
    return _convert_file_to_text(input_path, InputFormat.DOCX)

def convert_word_bytes_to_text(word_bytes: bytes, filename: str) -> str:
    """Converte o conteúdo de um arquivo Word (em bytes) para texto utilizando o docling.

    Args:
        word_bytes (bytes): Conteúdo do arquivo Word.
        filename (str): Nome do arquivo, utilizado para identificação.

    Returns:
        str: Texto convertido em formato markdown.

    Raises:
        Exception: Se a conversão do Word falhar.
    """
    return _process_bytes_with_temp_file(word_bytes, "docx", convert_word_file_to_text)
