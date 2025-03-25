import datetime
from dataclasses import dataclass
from django.test import TestCase
from core.exceptions import ApplicationError
from api.utils import (
    model_to_dataclass,
    dataclass_to_dict,
    list_models_to_dataclasses,
)

# Definindo um dataclass para teste
@dataclass
class DummyData:
    id: int
    name: str
    created: datetime.datetime

class DummyModel:
    def __init__(self, id, name, created):
        self.id = id
        self.name = name
        self.created = created
        self.extra = "ignore"

class UtilsTest(TestCase):
    """Testes para funções utilitárias de conversão de dados."""

    def test_model_to_dataclass(self):
        """Verifica se model_to_dataclass converte atributos corretamente."""
        created = datetime.datetime(2025, 3, 20, 12, 0)
        model_instance = DummyModel(1, "Teste", created)
        result = model_to_dataclass(model_instance, DummyData)
        self.assertEqual(result.id, 1)
        self.assertEqual(result.name, "Teste")
        self.assertEqual(result.created, created)
        # O campo 'extra' deve ser ignorado

    def test_dataclass_to_dict(self):
        """Verifica se dataclass_to_dict converte datetime para ISO string."""
        created = datetime.datetime(2025, 3, 20, 12, 0)
        instance = DummyData(1, "Teste", created)
        result = dataclass_to_dict(instance)
        self.assertEqual(result["created"], created.isoformat())

    def test_list_models_to_dataclasses(self):
        """Verifica se uma lista de instâncias é convertida corretamente para dataclasses."""
        created = datetime.datetime(2025, 3, 20, 12, 0)
        models = [DummyModel(1, "A", created), DummyModel(2, "B", created)]
        results = list_models_to_dataclasses(models, DummyData)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "A")
        self.assertEqual(results[1].id, 2)
