"""
Tipos para comparação de dados entre instrutor e alunos usando IA.
"""
from typing import Dict, Optional
from dataclasses import dataclass
from .base import JSONDict
from core.validators import validate_compare_request

# -----------------------------------------------------------------------------
# Tipos para Comparação da IA
# -----------------------------------------------------------------------------
@dataclass
class AIComparisonData:
    """Estrutura para requisição de comparação.
    
    Args:
        instructor: Dados do instrutor.
        students: Dados dos alunos.
    """
    instructor: JSONDict
    students: Dict[str, JSONDict]

    def __post_init__(self):
        """Valida os dados após inicialização.
        
        Raises:
            ValueError: Se os dados não estiverem no formato esperado.
        """
        result = validate_compare_request(self.__dict__)
        if not result.is_valid:
            raise ValueError(result.error_message)

@dataclass
class AISingleComparisonData:
    """Estrutura para requisição de comparação individual.
    
    Args:
        instructor: Dados do instrutor.
        student: Dados do aluno.
    """
    instructor: JSONDict
    student: JSONDict

@dataclass
class AIComparisonResponse:
    """Resposta de uma IA individual.
    
    Args:
        model_name: Nome do modelo utilizado.
        configurations: Configurações específicas.
        processing_time: Tempo de processamento.
        response: Resposta gerada pela IA.
        error: Erro ocorrido, se houver.
    """
    model_name: str
    configurations: JSONDict
    processing_time: float
    response: Optional[str] = None
    error: Optional[str] = None


AIComparisonResponseCollection = Dict[str, Dict[str, AIComparisonResponse]]
# Estrutura: {student_id: {ai_model_id: AIComparisonResponse}}
