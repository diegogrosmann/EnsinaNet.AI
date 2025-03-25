import json
from io import StringIO
from django.test import TestCase
from django.core.exceptions import ValidationError
from core.exceptions import FileProcessingError, APIClientError
from api.utils.validators import (
    validate_compare_request,
    validate_document_input,
    validate_training_data,
    validate_training_file,
)
from core.types.validation import ValidationResult

class ValidatorsTest(TestCase):
    """Testes para funções do módulo de validadores."""

    def test_validate_compare_request_valid(self):
        """Testa validação de dados de comparação válidos."""
        data = {
            "instructor": {"text": "Instrutor"},
            "students": {"s1": {"text": "Aluno 1"}, "s2": {"text": "Aluno 2"}}
        }
        result = validate_compare_request(data)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.data, data)

    def test_validate_compare_request_missing_instructor(self):
        """Testa validação quando 'instructor' está ausente."""
        data = {"students": {"s1": {"text": "Aluno 1"}}}
        result = validate_compare_request(data)
        self.assertFalse(result.is_valid)
        self.assertIn("instructor", result.error_message)

    def test_validate_document_input_valid(self):
        """Testa validação de entrada de documento válido."""
        data = {"name": "doc.pdf", "content": "dummycontent"}
        result = validate_document_input(data)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.data, data)

    def test_validate_document_input_invalid(self):
        """Testa validação de documento com dados faltando."""
        data = {"name": "doc.pdf"}
        result = validate_document_input(data)
        self.assertFalse(result.is_valid)
        self.assertIn("Conteúdo", result.error_message)

    def test_validate_training_data_valid(self):
        """Testa validação de dados de treinamento válidos."""
        valid_json = json.dumps([
            {"user_message": "Pergunta?", "response": "Resposta"}
        ])
        result = validate_training_data(valid_json)
        self.assertTrue(result.is_valid)
        self.assertIsInstance(result.data, list)
        self.assertEqual(len(result.data), 1)

    def test_validate_training_data_invalid_json(self):
        """Testa validação de dados de treinamento com JSON inválido."""
        invalid_json = "not a json"
        with self.assertRaises(ValidationError):
            validate_training_data(invalid_json, as_exception=True)

    def test_validate_training_file_valid(self):
        """Testa validação de arquivo de treinamento válido."""
        valid_content = json.dumps([
            {"user_message": "Pergunta?", "response": "Resposta"}
        ])
        file_obj = StringIO(valid_content)
        result = validate_training_file(file_obj)
        self.assertTrue(result.is_valid)
        self.assertIsInstance(result.data, list)

    def test_validate_training_file_invalid(self):
        """Testa validação de arquivo de treinamento com conteúdo inválido."""
        invalid_content = "invalid json"
        file_obj = StringIO(invalid_content)
        with self.assertRaises(FileProcessingError):
            validate_training_file(file_obj)
