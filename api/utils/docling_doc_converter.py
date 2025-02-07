import os
import tempfile
import logging
from pathlib import Path

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

_log = logging.getLogger(__name__)

# Tente importar o modelo de configuração do docling
try:
    from ai_config.models import DoclingConfiguration
except ImportError:
    DoclingConfiguration = None

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
    
    # Cria as opções padrão para o pipeline PDF
    pipeline_options = PdfPipelineOptions()
    
    # Se existir uma configuração definida, atualiza as opções
    if DoclingConfiguration:
        try:
            config_obj = DoclingConfiguration.objects.first()
        except Exception as e:
            _log.error(f"Erro ao obter DoclingConfiguration: {e}")
            config_obj = None
        
        if config_obj:
            pipeline_options.do_ocr = config_obj.do_ocr
            pipeline_options.do_table_structure = config_obj.do_table_structure
            pipeline_options.table_structure_options.do_cell_matching = config_obj.do_cell_matching
            if hasattr(pipeline_options, 'accelerator_options'):
                pipeline_options.accelerator_options.device = config_obj.accelerator_device
            if config_obj.custom_options:
                for key, value in config_obj.custom_options.items():
                    setattr(pipeline_options, key, value)
    
    doc_converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend
            )
        }
    )
    
    conv_result = doc_converter.convert(input_path)
    if conv_result:
        return conv_result.document.export_to_markdown()
    else:
        raise Exception("Falha na conversão do PDF utilizando docling.")

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
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(pdf_bytes)
        temp_path = temp_file.name

    try:
        text = convert_pdf_file_to_text(temp_path)
    finally:
        os.remove(temp_path)
    return text

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
    
    doc_converter = DocumentConverter(
        allowed_formats=[InputFormat.DOCX]  # Suporte para DOCX
    )
    
    conv_result = doc_converter.convert(input_path)
    if conv_result:
        return conv_result.document.export_to_markdown()
    else:
        raise Exception("Falha na conversão do Word utilizando docling.")

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
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
        temp_file.write(word_bytes)
        temp_path = temp_file.name

    try:
        text = convert_word_file_to_text(temp_path)
    finally:
        os.remove(temp_path)
    return text
