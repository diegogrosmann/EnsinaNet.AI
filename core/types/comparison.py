"""
Tipos para comparação de dados entre instrutor e alunos usando IA.

Define estruturas de dados para solicitações de comparação
e para armazenar os resultados das comparações.
"""
from datetime import datetime
import logging
from typing import Dict, Optional, List, Any, Type
from dataclasses import dataclass

from core.exceptions import CoreValueException
from core.types.app_response import APPResponse
from core.types.errors import ComparisonError
from core.types.ai import AIResponseDict
from core.types.base import DataModelDict, ResultModel, TDataModel
from core.types.operation import OperationData, OperationType
from core.types.status import EntityStatus
from core.types.task import QueueableTask, AsyncTask
from core.validators import validate_compare_request
from core.types.ai import AIResponseDict

from . import DataModel, JSONDict

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para Requisição 
# -----------------------------------------------------------------------------
class ComparisonRequestData(DataModel):
    """Estrutura para requisição de comparação.
    
    Contém os dados necessários para realizar uma comparação entre
    as respostas do instrutor e de múltiplos alunos.
    
    Args:
        instructor: Dados do instrutor (resposta referência).
        students: Dicionário de dados dos alunos, indexado por identificador.
    """
    instructor: JSONDict
    students: Dict[str, JSONDict]
    
    def __init__(self, instructor: JSONDict, students: Dict[str, JSONDict]):
        """Inicializa com dados do instrutor e estudantes"""
        super().__init__()
        self.instructor = instructor
        self.students = students

    def __post_init__(self):
        """Valida os dados após inicialização.
        
        Raises:
            ComparisonError: Se os dados não estiverem no formato esperado.
        """
        try:
            result = validate_compare_request(self.__dict__)
            if not result.is_valid:
                logger.error(f"Validação de dados de comparação falhou: {result.error_message}")
                raise ComparisonError(
                    message=result.error_message, 
                    status_code=400,
                    phase="validação"
                )
                
            student_count = len(self.students)
            logger.info(f"AIComparisonData criado com {student_count} alunos")
            
        except Exception as e:
            if not isinstance(e, ComparisonError):
                logger.error(f"Erro ao validar dados de comparação: {str(e)}", exc_info=True)
                raise ComparisonError(
                    message=f"Dados de comparação inválidos: {str(e)}", 
                    status_code=400,
                    phase="validação"
                )
            raise
    
    def to_dict(self) -> JSONDict:
        """Converte os dados de comparação para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os dados de comparação.
        """
        logger.debug("Convertendo AIComparisonData para dicionário")
        base_dict = super().to_dict()
        base_dict.update({
            "instructor": self.instructor,
            "students": self.students
        })
        return base_dict
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ComparisonRequestData':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com dados para criar o objeto.
            
        Returns:
            ComparisonRequestData: Nova instância criada a partir dos dados.
        """
        return cls(
            instructor=data.get('instructor', {}),
            students=data.get('students', {})
        )
        
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


class SingleComparisonRequestData(DataModel):
    """Estrutura para requisição de comparação de um único aluno.
    
    Otimizada para o caso comum de comparar apenas um aluno com o instrutor,
    simplificando a interface e o processamento.
    
    Args:
        instructor: Dados do instrutor (resposta referência).
        student_id: Identificador único do aluno.
        student: Dados do aluno a ser comparado.
    """
    instructor: JSONDict
    student_id: str
    student: JSONDict
    
    def __init__(self, instructor: JSONDict, student_id: str, student: JSONDict):
        """Inicializa com dados do instrutor e um único aluno"""
        super().__init__()
        self.instructor = instructor
        self.student_id = student_id
        self.student = student

    def __post_init__(self):
        """Valida os dados após inicialização.
        
        Raises:
            ComparisonError: Se os dados não estiverem no formato esperado.
        """
        try:
            # Convertemos para o formato esperado pelo validador existente
            data_dict = self.__dict__.copy()
            data_dict["students"] = {self.student_id: self.student}
            del data_dict["student_id"]
            del data_dict["student"]
            
            result = validate_compare_request(data_dict)
            if not result.is_valid:
                logger.error(f"Validação de dados de comparação falhou: {result.error_message}")
                raise ComparisonError(
                    message=result.error_message, 
                    status_code=400,
                    phase="validação",
                    student_id=self.student_id
                )
                
            logger.info(f"SingleComparisonData criado para o aluno: {self.student_id}")
            
        except Exception as e:
            if not isinstance(e, ComparisonError):
                logger.error(f"Erro ao validar dados de comparação: {str(e)}", exc_info=True)
                raise ComparisonError(
                    message=f"Dados de comparação inválidos: {str(e)}", 
                    status_code=400,
                    phase="validação",
                    student_id=self.student_id
                )
            raise
        
    def to_comparison_request_data(self) -> ComparisonRequestData:
        """Converte para o formato de dados de comparação múltipla.
        
        Útil quando é necessário usar uma implementação existente que
        espera o formato de comparação com múltiplos alunos.
        
        Returns:
            ComparisonRequestData: Objeto no formato de múltiplos alunos.
        """
        students = {self.student_id: self.student}
        return ComparisonRequestData(
            instructor=self.instructor,
            students=students
        )


class ComparisonDict(DataModelDict[AIResponseDict]):
    """Dicionário tipo-seguro para dados de comparação.
    
    Armazena respostas de IA para diferentes comparações, indexadas por identificador
    (como ID de aluno).
    
    Estrutura:
        "student_id" = AIResponseDict
    """
    
@dataclass
class ComparisonTask(QueueableTask):
    """Tarefa assíncrona específica para comparações.
    
    Especializa AsyncTask para o caso específico de comparações,
    com métodos e propriedades específicas para este tipo de operação.
    
    Attributes:
        compare_data (ComparisonRequestData): Dados de entrada para a comparação.
    """
    input_data: ComparisonRequestData = None
    result: Optional[ComparisonDict] = None
    
    def __post_init__(self):
        """Inicializa dados específicos para comparações."""
        # Definimos a função dummy antes de chamar super().__post_init__
        if self.func is None:
            self.func = lambda: None
            
        super().__post_init__()
        
        # Validar que compare_data foi fornecido
        if not self.compare_data:
            raise CoreValueException(
                "Dados de comparação são obrigatórios",
                field="compare_data", 
                type_name="ComparisonTask"
            )
        
        if self.compare_data:
            self.input_data = self.compare_data
            
        # Calcula estatísticas da tarefa
        if self.input_data and isinstance(self.input_data, dict):
            students_count = len(self.input_data.get("students", {}))
            logger.info(f"ComparisonTask {self.task_id} criada com {students_count} alunos")
    
    @property
    def student_count(self) -> int:
        """Retorna o número de alunos na comparação.
        
        Returns:
            int: Número de alunos a serem comparados.
        """
        if not self.input_data or not isinstance(self.input_data, dict):
            return 0
        return len(self.input_data.get("students", {}))
    
    @property
    def is_large_task(self) -> bool:
        """Verifica se é uma tarefa grande que deve ser processada com prioridade baixa.
        
        Returns:
            bool: True se for uma tarefa grande.
        """
        return self.student_count > 5
    
    def get_summary(self) -> JSONDict:
        """Retorna um resumo da tarefa de comparação.
        
        Returns:
            JSONDict: Resumo com informações principais da tarefa.
        """
        base_dict = self.to_dict()
        base_dict["student_count"] = self.student_count
        base_dict["is_large_task"] = self.is_large_task
        
        # Remove dados completos de entrada e resultado para economizar espaço
        if "input_data" in base_dict:
            del base_dict["input_data"]
            
        # Em vez do resultado completo, fornecer apenas informações básicas
        if self.status == EntityStatus.COMPLETED and self.result is not None:
            # Extrair dados do DataModelDict
            result_dict = self.result.to_dict() if hasattr(self.result, 'to_dict') else {}
            
            # Comportamento especial para DataModelDict
            if isinstance(self.result, DataModelDict):
                student_ids = list(self.result.keys())
                ai_models = set()
                
                for student_id, student_data in self.result.items():
                    if hasattr(student_data, 'to_dict'):
                        student_dict = student_data.to_dict()
                        ai_models.update(student_dict.keys())
                    else:
                        # Fallback para casos onde os itens não são DataModel
                        ai_models.update(student_data.keys() if isinstance(student_data, dict) else [])
            else:
                # Compatibilidade com o formato anterior (Dict[str, Any])
                result_data = result_dict.get("students", {})
                student_ids = list(result_data.keys())
                ai_models = set()
                
                for student_data in result_data.values():
                    ai_models.update(student_data.keys() if isinstance(student_data, dict) else [])
            
            # Substitua o resultado completo por um resumo
            base_dict["result_summary"] = {
                "student_count": len(student_ids),
                "student_ids": student_ids[:5] + ["..."] if len(student_ids) > 5 else student_ids,
                "ai_model_count": len(ai_models),
                "ai_models": list(ai_models)[:5] + ["..."] if len(ai_models) > 5 else list(ai_models)
            }
            
            if "result" in base_dict:
                del base_dict["result"]
                
        return base_dict
    

@dataclass
class AsyncComparisonTask(AsyncTask):
    """Tarefa assíncrona específica para comparações.
    
    Especializa AsyncTask para o caso específico de comparações assíncronas,
    com métodos e propriedades específicas para este tipo de operação.
    
    Attributes:
        compare_data (ComparisonRequestData): Dados de entrada para a comparação.
    """
    input_data: ComparisonRequestData = None
    
@dataclass
class ComparisonJob(OperationData):
    """Job de comparação que executa a lógica de comparação."""

    operation_type: Optional[OperationType] = OperationType.COMPARISON

