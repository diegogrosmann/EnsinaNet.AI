"""
Tipos para comparação de dados entre instrutor e alunos usando IA.

Define estruturas de dados para solicitações de comparação
e para armazenar os resultados das comparações.
"""
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field, asdict
from .base import JSONDict
from .validation import ValidationResult
from .result import OperationResult
from core.exceptions import APIError, AIConfigError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para Comparação da IA
# -----------------------------------------------------------------------------
@dataclass
class AIComparisonData:
    """Estrutura para requisição de comparação.
    
    Contém os dados necessários para realizar uma comparação entre
    as respostas do instrutor e de múltiplos alunos.
    
    Args:
        instructor: Dados do instrutor (resposta referência).
        students: Dicionário de dados dos alunos, indexado por identificador.
    """
    instructor: JSONDict
    students: Dict[str, JSONDict]

    def __post_init__(self):
        """Valida os dados após inicialização.
        
        Raises:
            APIError: Se os dados não estiverem no formato esperado.
        """
        try:
            from core.validators import validate_compare_request
            result = validate_compare_request(self.__dict__)
            if not result.is_valid:
                logger.error(f"Validação de dados de comparação falhou: {result.error_message}")
                raise APIError(result.error_message, status_code=400)
                
            student_count = len(self.students)
            logger.info(f"AIComparisonData criado com {student_count} alunos")
            
        except Exception as e:
            if not isinstance(e, APIError):
                logger.error(f"Erro ao validar dados de comparação: {str(e)}", exc_info=True)
                raise APIError(f"Dados de comparação inválidos: {str(e)}", status_code=400)
            raise
    
    def to_dict(self) -> JSONDict:
        """Converte os dados de comparação para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os dados de comparação.
        """
        logger.debug("Convertendo AIComparisonData para dicionário")
        return {
            "instructor": self.instructor,
            "students": self.students
        }
        
    def get_student_names(self) -> List[str]:
        """Retorna a lista de identificadores dos alunos.
        
        Returns:
            List[str]: Lista de identificadores dos alunos.
        """
        return list(self.students.keys())
        
    def get_student_count(self) -> int:
        """Retorna o número de alunos incluídos na comparação.
        
        Returns:
            int: Número de alunos.
        """
        return len(self.students)

@dataclass
class AISingleComparisonData:
    """Estrutura para requisição de comparação individual.
    
    Contém os dados para comparar a resposta de um único aluno
    com a resposta de referência do instrutor.
    
    Args:
        instructor: Dados do instrutor (resposta referência).
        student: Dados do aluno a ser avaliado.
        student_id: Identificador do aluno (opcional).
    """
    instructor: JSONDict
    student: JSONDict
    student_id: Optional[str] = None

    def __post_init__(self):
        """Valida os dados após inicialização."""
        if not self.instructor:
            logger.warning("AISingleComparisonData criado com instructor vazio")
            
        if not self.student:
            logger.warning("AISingleComparisonData criado com student vazio")
            
        logger.debug(f"AISingleComparisonData criado para aluno {self.student_id or 'sem ID'}")
        
    def to_dict(self) -> JSONDict:
        """Converte os dados de comparação individual para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os dados de comparação.
        """
        result = {
            "instructor": self.instructor,
            "student": self.student
        }
        if self.student_id:
            result["student_id"] = self.student_id
        return result

@dataclass
class AIComparisonResponse:
    """Resposta de uma IA individual para uma comparação.
    
    Contém o resultado de uma comparação feita por um modelo de IA específico,
    incluindo o texto da resposta e métricas de processamento.
    
    Args:
        model_name: Nome do modelo de IA utilizado.
        configurations: Configurações específicas utilizadas.
        processing_time: Tempo de processamento em segundos.
        response: Resposta gerada pela IA.
        thinking: Texto de pensamento gerado pela IA (opcional).
        error: Erro ocorrido durante o processamento, se houver.
    """
    model_name: str
    configurations: JSONDict
    processing_time: float
    response: Optional[str] = None
    thinking: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Valida os dados após inicialização."""
        if not self.response and not self.error:
            logger.warning(f"AIComparisonResponse criado sem response e sem error para modelo {self.model_name}")
        
        if self.error:
            logger.info(f"AIComparisonResponse com erro para modelo {self.model_name}: {self.error}")
        else:
            logger.debug(f"AIComparisonResponse criado para modelo {self.model_name} "
                         f"(tempo: {self.processing_time:.3f}s)")
    
    def to_dict(self) -> JSONDict:
        """Converte a resposta de comparação para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os dados da resposta.
        """
        return {
            "model_name": self.model_name,
            "configurations": self.configurations,
            "processing_time": self.processing_time,
            "response": self.response,
            "error": self.error
        }
    
    @classmethod
    def from_error(cls, model_name: str, error_message: str, 
                  configurations: Optional[Dict[str, Any]] = None) -> 'AIComparisonResponse':
        """Cria uma resposta de comparação a partir de um erro.
        
        Args:
            model_name: Nome do modelo que gerou o erro.
            error_message: Mensagem de erro.
            configurations: Configurações utilizadas (opcional).
            
        Returns:
            AIComparisonResponse: Instância com os dados de erro.
        """
        logger.error(f"Criando AIComparisonResponse de erro para modelo {model_name}: {error_message}")
        return cls(
            model_name=model_name,
            configurations=configurations or {},
            processing_time=0.0,
            error=error_message
        )

    def to_operation_result(self) -> OperationResult[str]:
        """Converte a resposta para um OperationResult.
        
        Returns:
            OperationResult: Resultado da operação.
        """
        if self.error:
            return OperationResult.failed(self.error)
        return OperationResult.succeeded(self.response)


AIComparisonResponseCollection = Dict[str, Dict[str, AIComparisonResponse]]
"""
Coleção de respostas de comparação organizada por aluno e modelo.
Estrutura: {student_id: {ai_model_id: AIComparisonResponse}}
"""
