import datetime
from dataclasses import dataclass
from django.test import TestCase
from core.types.base import JSONDict, T, Result
from core.types.ai import AIMessage, AISuccess, AIPromptConfig, AIConfig
from core.types.comparison import AIComparisonData, AISingleComparisonData, AIComparisonResponse
from core.types.api_response import APPResponse, APIComparisonResponse
from core.types.validation import ValidationResult

@dataclass
class DummyData:
    id: int
    name: str
    created: datetime.datetime

class TypesTest(TestCase):
    """Testes para os tipos e estruturas de dados."""

    def test_result_success_and_failure(self):
        """Testa a classe Result para cenários de sucesso e falha."""
        res_success = Result.success("valor")
        self.assertTrue(res_success.is_success)
        self.assertEqual(res_success.value, "valor")
        res_failure = Result.failure("erro")
        self.assertFalse(res_failure.is_success)
        with self.assertRaises(ValueError):
            _ = res_failure.value

    def test_ai_message_to_dict(self):
        """Testa a conversão de AIMessage para dicionário."""
        msg = AIMessage(system_message="Instrução", user_message="Pergunta")
        d = msg.to_dict()
        self.assertEqual(d["system_message"], "Instrução")
        self.assertEqual(d["user_message"], "Pergunta")

    def test_ai_comparison_data(self):
        """Testa criação e métodos de AIComparisonData."""
        data = {
            "instructor": {"text": "ref"},
            "students": {"s1": {"text": "a1"}, "s2": {"text": "a2"}}
        }
        comp_data = AIComparisonData(**data)
        self.assertEqual(comp_data.get_student_count(), 2)
        self.assertEqual(set(comp_data.get_student_names()), {"s1", "s2"})

    def test_app_response_methods(self):
        """Testa os métodos de APPResponse."""
        success_resp = APPResponse.success_response(data={"key": "value"})
        self.assertTrue(success_resp.success)
        self.assertEqual(success_resp.to_dict()["data"]["key"], "value")
        error_resp = APPResponse.error_response("Erro de teste")
        self.assertFalse(error_resp.success)
        self.assertEqual(error_resp.to_dict()["error"], "Erro de teste")

    def test_validation_result_as_dict(self):
        """Testa a conversão de ValidationResult para dicionário."""
        valid_result = ValidationResult(True, data={"campo": "valor"})
        d = valid_result.as_dict()
        self.assertTrue(d["valid"])
        self.assertIn("data", d)
        invalid_result = ValidationResult(False, error_message="Erro")
        d2 = invalid_result.as_dict()
        self.assertFalse(d2["valid"])
        self.assertEqual(d2["error"], "Erro")
