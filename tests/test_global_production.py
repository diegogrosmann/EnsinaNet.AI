# tests/test_global_production.py

import base64
import io
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from dataclasses import dataclass

from django.test import TestCase, SimpleTestCase, RequestFactory, override_settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpRequest, HttpResponse, HttpResponseRedirect

from unittest.mock import patch, MagicMock

# Importações dos módulos a serem testados
from core.utils.document import extract_metadata
from core.exceptions import FileProcessingError, APIError, ApplicationError, MissingAPIKeyError
from core.utils.doc_extractor import extract_text, _get_file_extension
from core.utils.docling_doc_converter import (
    _convert_file_to_text,
    _process_bytes_with_temp_file,
    convert_pdf_file_to_text,
    convert_pdf_bytes_to_text,
    convert_word_file_to_text,
    convert_word_bytes_to_text,
)
from api.utils import model_to_dataclass, dataclass_to_dict, list_models_to_dataclasses
from core.exceptions import GlobalExceptionMiddleware
from core.validators import (
    validate_compare_request,
    validate_document_input,
    validate_training_data,
    validate_training_file,
)

from core.types.base import JSONDict, Result
from core.types.ai import AIMessage, AISuccess, AIPromptConfig, AIConfig
from core.types.comparison import AIComparisonData, AISingleComparisonData, AIComparisonResponse
from core.types.app_response import APPResponse, APIComparisonResponse
from core.types.validation import ValidationResult
from core.types.circuit_breaker import CircuitState, CircuitBreakerConfig, CircuitBreakerMetrics

# --------------------------------------------------------------------------
# Testes para utils/doc_extractor.py
# --------------------------------------------------------------------------
class GlobalProductionDocExtractorTest(TestCase):
    """Testes globais de produção para o módulo de extração de texto de documentos."""

    def test_get_file_extension_production(self):
        """Verifica se a função extrai corretamente a extensão do arquivo."""
        self.assertEqual(_get_file_extension("test.PDF"), "pdf")
        self.assertEqual(_get_file_extension("report.docx"), "docx")
        self.assertEqual(_get_file_extension("archive"), "")

    @patch("api.utils.doc_extractor.convert_pdf_bytes_to_text", return_value="Converted PDF Text")
    def test_extract_text_pdf_production(self, mock_pdf_converter):
        """Testa extração de texto de um PDF válido."""
        sample_bytes = b"%PDF-dummy content"
        sample_b64 = base64.b64encode(sample_bytes).decode("utf-8")
        data = {"name": "document.pdf", "content": sample_b64}
        result = extract_text(data)
        self.assertEqual(result, "Converted PDF Text")
        mock_pdf_converter.assert_called_once()

    @patch("api.utils.doc_extractor.convert_word_bytes_to_text", return_value="Converted DOCX Text")
    def test_extract_text_docx_production(self, mock_docx_converter):
        """Testa extração de texto de um DOCX válido."""
        sample_bytes = b"dummy docx content"
        sample_b64 = base64.b64encode(sample_bytes).decode("utf-8")
        data = {"name": "report.docx", "content": sample_b64}
        result = extract_text(data)
        self.assertEqual(result, "Converted DOCX Text")
        mock_docx_converter.assert_called_once()

    def test_extract_text_invalid_extension(self):
        """Verifica que extensões não suportadas geram erro."""
        sample_bytes = b"dummy content"
        sample_b64 = base64.b64encode(sample_bytes).decode("utf-8")
        data = {"name": "file.txt", "content": sample_b64}
        with self.assertRaises(FileProcessingError) as cm:
            extract_text(data)
        self.assertIn("Formato de arquivo não suportado", str(cm.exception))

    def test_extract_text_invalid_base64(self):
        """Verifica que conteúdo base64 inválido gera erro."""
        data = {"name": "document.pdf", "content": "not_base64!!"}
        with self.assertRaises(FileProcessingError) as cm:
            extract_text(data)
        self.assertIn("base64 inválido", str(cm.exception))


# --------------------------------------------------------------------------
# Testes para utils/docling_doc_converter.py
# --------------------------------------------------------------------------
class GlobalProductionDoclingDocConverterTest(TestCase):
    """Testes globais de produção para o módulo de conversão de documentos via Docling."""

    def dummy_converter(self, file_path: str) -> str:
        """Função dummy para simular conversão: lê o arquivo e retorna o conteúdo em maiúsculas."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().upper()

    def test_process_bytes_with_temp_file_production(self):
        """Testa que _process_bytes_with_temp_file processa os bytes e remove o arquivo temporário."""
        test_bytes = b"example content"
        result = _process_bytes_with_temp_file(test_bytes, "txt", self.dummy_converter)
        self.assertEqual(result, "EXAMPLE CONTENT")
        # O arquivo temporário é removido (não existe mais)

    @patch("api.utils.docling_doc_converter.DocumentConverter")
    def test_convert_file_to_text_production(self, mock_doc_converter_class):
        """Testa _convert_file_to_text simulando uma conversão bem-sucedida."""
        dummy_document = MagicMock()
        dummy_document.export_to_markdown.return_value = "Markdown Content"
        instance = MagicMock()
        instance.convert.return_value = dummy_document
        mock_doc_converter_class.return_value = instance

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as temp_file:
            temp_file.write("dummy file content")
            temp_path = temp_file.name

        try:
            result = _convert_file_to_text(Path(temp_path), "pdf")
            self.assertEqual(result, "Markdown Content")
        finally:
            os.unlink(temp_path)

    @patch("api.utils.docling_doc_converter._process_bytes_with_temp_file", return_value="Processed PDF Text")
    def test_convert_pdf_bytes_to_text_production(self, mock_process):
        """Testa convert_pdf_bytes_to_text delegando para _process_bytes_with_temp_file."""
        sample_bytes = b"pdf bytes"
        result = convert_pdf_bytes_to_text(sample_bytes, "sample.pdf")
        self.assertEqual(result, "Processed PDF Text")
        mock_process.assert_called_once()

    @patch("api.utils.docling_doc_converter._process_bytes_with_temp_file", return_value="Processed DOCX Text")
    def test_convert_word_bytes_to_text_production(self, mock_process):
        """Testa convert_word_bytes_to_text delegando para _process_bytes_with_temp_file."""
        sample_bytes = b"docx bytes"
        result = convert_word_bytes_to_text(sample_bytes, "sample.docx")
        self.assertEqual(result, "Processed DOCX Text")
        mock_process.assert_called_once()


# --------------------------------------------------------------------------
# Testes para utils.py (funções de conversão de modelo e dataclass)
# --------------------------------------------------------------------------
class GlobalProductionUtilsTest(TestCase):
    """Testes globais para funções de utilitários de conversão e manipulação de dados."""

    @dataclass
    class DummyData:
        id: int
        name: str
        created: datetime

    class DummyModel:
        def __init__(self, id, name, created):
            self.id = id
            self.name = name
            self.created = created
            self.extra = "ignore"

    def test_model_to_dataclass_production(self):
        """Verifica se model_to_dataclass converte os atributos corretos."""
        created = datetime(2025, 1, 1, 12, 0)
        instance = self.DummyModel(1, "Test", created)
        result = model_to_dataclass(instance, self.DummyData)
        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "Test")
        self.assertEqual(result.created, created)

    def test_dataclass_to_dict_production(self):
        """Verifica se dataclass_to_dict converte datetime para string ISO."""
        created = datetime(2025, 1, 1, 12, 0)
        dummy = self.DummyData(1, "Test", created)
        result = dataclass_to_dict(dummy)
        self.assertEqual(result["created"], created.isoformat())

    def test_list_models_to_dataclasses_production(self):
        """Testa a conversão de uma lista de modelos para uma lista de dataclasses."""
        created = datetime(2025, 1, 1, 12, 0)
        models = [self.DummyModel(1, "A", created), self.DummyModel(2, "B", created)]
        result = list_models_to_dataclasses(models, self.DummyData)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "A")
        self.assertEqual(result[1].id, 2)


# --------------------------------------------------------------------------
# Testes para Global Exception Middleware
# --------------------------------------------------------------------------
class GlobalProductionGlobalExceptionMiddlewareTest(TestCase):
    """Testes globais para o middleware de exceções global (produção)."""

    def setUp(self):
        self.factory = RequestFactory()
        # Define uma função dummy que sempre lança exceção
        def dummy_get_response(request):
            raise Exception("Production test exception")
        self.middleware = GlobalExceptionMiddleware(dummy_get_response)

    @override_settings(DEBUG=True)
    def test_ajax_exception_response_production(self):
        """Testa resposta JSON detalhada em requisição AJAX com DEBUG=True."""
        request = self.factory.get("/test/")
        request.META["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        request.user = type("DummyUser", (), {"is_authenticated": True, "username": "produser"})
        response = self.middleware(request)
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertIn("Production test exception", data["error"]["message"])
        self.assertIn("traceback", data["error"])

    def test_non_ajax_exception_response_production(self):
        """Testa redirecionamento em requisição não-AJAX quando ocorre exceção."""
        request = self.factory.get("/test/", HTTP_REFERER="/back/")
        request.user = type("DummyUser", (), {"is_authenticated": True, "username": "produser"})
        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/back/")


# --------------------------------------------------------------------------
# Testes para utils/validators.py
# --------------------------------------------------------------------------
class GlobalProductionValidatorsTest(TestCase):
    """Testes globais para as funções do módulo de validadores."""

    def test_validate_compare_request_valid(self):
        data = {"instructor": {"text": "teacher"}, "students": {"s1": {"text": "student"}}}
        result = validate_compare_request(data)
        self.assertTrue(result.is_valid)

    def test_validate_compare_request_invalid(self):
        data = {"students": {"s1": {"text": "student"}}}
        result = validate_compare_request(data)
        self.assertFalse(result.is_valid)
        self.assertIn("instructor", result.error_message)

    def test_validate_document_input_valid(self):
        data = {"name": "doc.pdf", "content": "dummy"}
        result = validate_document_input(data)
        self.assertTrue(result.is_valid)

    def test_validate_document_input_invalid(self):
        data = {"name": "doc.pdf"}
        result = validate_document_input(data)
        self.assertFalse(result.is_valid)
        self.assertIn("Conteúdo", result.error_message)

    def test_validate_training_data_valid(self):
        valid_data = json.dumps([{"user_message": "Q?", "response": "A"}])
        result = validate_training_data(valid_data)
        self.assertTrue(result.is_valid)
        self.assertIsInstance(result.data, list)

    def test_validate_training_data_invalid(self):
        invalid_data = "invalid json"
        with self.assertRaises(ValidationError):
            validate_training_data(invalid_data, as_exception=True)

    def test_validate_training_file_valid(self):
        valid_data = json.dumps([{"user_message": "Q?", "response": "A"}])
        file_obj = io.StringIO(valid_data)
        result = validate_training_file(file_obj)
        self.assertTrue(result.is_valid)

    def test_validate_training_file_invalid(self):
        invalid_data = "not json"
        file_obj = io.StringIO(invalid_data)
        with self.assertRaises(FileProcessingError):
            validate_training_file(file_obj)


# --------------------------------------------------------------------------
# Testes para document.py
# --------------------------------------------------------------------------
class GlobalProductionDocumentTest(TestCase):
    """Testes globais para o módulo document.py (processamento de metadados e conteúdo)."""

    def test_extract_metadata_production(self):
        # Cria dados fictícios com conteúdo base64
        sample_content = "dummy content for testing"
        sample_b64 = base64.b64encode(sample_content.encode("utf-8")).decode("utf-8")
        file_data = {"name": "sample.pdf", "content": sample_b64}
        metadata = extract_metadata(file_data)
        self.assertEqual(metadata.filename, "sample.pdf")
        self.assertEqual(metadata.mime_type, "application/pdf")
        self.assertGreater(metadata.size_bytes, 0)

# --------------------------------------------------------------------------
# Testes para tipos (global production)
# --------------------------------------------------------------------------
class GlobalProductionTypesTest(TestCase):
    """Testes globais para os módulos de tipos (base, ai, comparison, api_response, etc.)."""

    def test_result_success_failure(self):
        res = Result.success("ok")
        self.assertTrue(res.is_success)
        self.assertEqual(res.value, "ok")
        res_fail = Result.failure("error")
        self.assertFalse(res_fail.is_success)
        with self.assertRaises(ValueError):
            _ = res_fail.value

    def test_ai_message_to_dict(self):
        msg = AIMessage(system_message="sys", user_message="user")
        d = msg.to_dict()
        self.assertEqual(d["system_message"], "sys")
        self.assertEqual(d["user_message"], "user")

    def test_app_response_to_dict(self):
        resp = APPResponse(success=True, data={"key": "value"})
        d = resp.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["data"]["key"], "value")


# Você pode expandir com testes para outros módulos de tipos conforme necessário.
