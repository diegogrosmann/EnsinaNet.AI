import base64
from unittest.mock import patch
from django.test import TestCase
from core.exceptions import FileProcessingError
from api.utils.doc_extractor import _get_file_extension, extract_text

class DocExtractorTest(TestCase):
    """Testes para funções de extração de texto de documentos."""

    def test_get_file_extension(self):
        """Verifica se a função extrai corretamente a extensão do arquivo."""
        self.assertEqual(_get_file_extension("document.PDF"), "pdf")
        self.assertEqual(_get_file_extension("file.docx"), "docx")
        self.assertEqual(_get_file_extension("no_extension"), "")

    @patch("api.utils.doc_extractor.convert_pdf_bytes_to_text", return_value="Texto extraído do PDF")
    def test_extract_text_pdf(self, mock_pdf_converter):
        """Testa extração de texto de um documento PDF válido."""
        sample_content = base64.b64encode(b"%PDF-1.4 dummy pdf content").decode("utf-8")
        data = {"name": "document.pdf", "content": sample_content}
        result = extract_text(data)
        self.assertEqual(result, "Texto extraído do PDF")
        mock_pdf_converter.assert_called_once()

    @patch("api.utils.doc_extractor.convert_word_bytes_to_text", return_value="Texto extraído do DOCX")
    def test_extract_text_docx(self, mock_docx_converter):
        """Testa extração de texto de um documento DOCX válido."""
        sample_content = base64.b64encode(b"dummy docx content").decode("utf-8")
        data = {"name": "file.docx", "content": sample_content}
        result = extract_text(data)
        self.assertEqual(result, "Texto extraído do DOCX")
        mock_docx_converter.assert_called_once()

    def test_extract_text_missing_fields(self):
        """Testa extração com dados incompletos, esperando erro."""
        data = {"name": "file.pdf"}  # content ausente
        with self.assertRaises(FileProcessingError) as context:
            extract_text(data)
        self.assertIn("Conteúdo", str(context.exception))

    def test_extract_text_invalid_base64(self):
        """Testa extração quando o conteúdo não é base64 válido."""
        data = {"name": "file.pdf", "content": "!!!invalid-base64!!!"}
        with self.assertRaises(FileProcessingError) as context:
            extract_text(data)
        self.assertIn("base64 inválido", str(context.exception))
