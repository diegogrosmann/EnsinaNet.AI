import os
import io
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import TestCase
from core.exceptions import FileProcessingError
from api.utils.docling_doc_converter import (
    _convert_file_to_text,
    _process_bytes_with_temp_file,
    convert_pdf_file_to_text,
    convert_pdf_bytes_to_text,
    convert_word_file_to_text,
    convert_word_bytes_to_text,
)

class DoclingDocConverterTest(TestCase):
    """Testes para o módulo de conversão de documentos com docling."""

    def dummy_converter(self, file_path):
        """Função dummy que lê o arquivo e retorna o conteúdo em maiúsculas."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().upper()

    def test_process_bytes_with_temp_file(self):
        """Testa que a função _process_bytes_with_temp_file utiliza o arquivo temporário e o remove."""
        test_bytes = b"conteudo de teste"
        result = _process_bytes_with_temp_file(test_bytes, "txt", self.dummy_converter)
        self.assertEqual(result, "CONTEUDO DE TESTE")
        # O arquivo temporário deve ter sido removido automaticamente

    @patch("api.utils.docling_doc_converter.DocumentConverter")
    def test_convert_file_to_text(self, mock_converter_class):
        """Testa _convert_file_to_text simulando uma conversão bem-sucedida."""
        # Cria um dummy objeto converter com método convert()
        dummy_document = MagicMock()
        dummy_document.export_to_markdown.return_value = "dummy markdown"
        instance = MagicMock()
        instance.convert.return_value = dummy_document
        mock_converter_class.return_value = instance

        # Cria um arquivo temporário
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as temp_file:
            temp_file.write("dummy content")
            temp_path = temp_file.name

        try:
            result = _convert_file_to_text(Path(temp_path), "pdf")
            self.assertEqual(result, "dummy markdown")
        finally:
            os.unlink(temp_path)

    @patch("api.utils.docling_doc_converter._process_bytes_with_temp_file")
    def test_convert_pdf_bytes_to_text(self, mock_process):
        """Testa convert_pdf_bytes_to_text chamando _process_bytes_with_temp_file."""
        mock_process.return_value = "PDF em markdown"
        test_bytes = b"dummy pdf bytes"
        result = convert_pdf_bytes_to_text(test_bytes, "teste.pdf")
        self.assertEqual(result, "PDF em markdown")
        mock_process.assert_called_once_with(test_bytes, "pdf", convert_pdf_file_to_text)

    @patch("api.utils.docling_doc_converter._process_bytes_with_temp_file")
    def test_convert_word_bytes_to_text(self, mock_process):
        """Testa convert_word_bytes_to_text chamando _process_bytes_with_temp_file."""
        mock_process.return_value = "DOCX em markdown"
        test_bytes = b"dummy docx bytes"
        result = convert_word_bytes_to_text(test_bytes, "teste.docx")
        self.assertEqual(result, "DOCX em markdown")
        mock_process.assert_called_once_with(test_bytes, "docx", convert_word_file_to_text)
