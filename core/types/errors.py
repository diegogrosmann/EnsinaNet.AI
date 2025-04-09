"""
Definições centralizadas de erros para toda a aplicação.

Contém modelos de erro padronizados para uso em diferentes contextos
da aplicação, garantindo consistência no tratamento de erros.
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.types.base import ErrorModel

logger = logging.getLogger(__name__)

# Tipo para dados adicionais em JSON
JSONDict = Dict[str, Any]


@dataclass
class APPError(ErrorModel):
    """Implementação padrão de ErrorModel para erros de aplicação.
    
    Attributes:
        Herda todos os atributos de ErrorModel.
    """
    def handle(self) -> None:
        """Implementação padrão para lidar com o erro.
        
        Registra o erro utilizando o logger configurado.
        """
        logger.error(f"Erro na aplicação (ID: {self.error_id}): {self.message}", exc_info=True)

@dataclass
class TaskError(ErrorModel):
    """Modelo de erro específico para tarefas.
    
    Representa erros relacionados a execução e processamento de tarefas.
    
    Attributes:
        message: Mensagem de erro legível para humanos.
        code: Código de erro opcional para identificação programática.
        error_id: ID único para rastreamento do erro.
        status_code: Código de status HTTP associado ao erro.
        task_id: ID da tarefa relacionada ao erro (opcional).
    """
    task_id: Optional[str] = None

@dataclass
class CircuitBreakerError(ErrorModel):
    """Modelo de erro específico para operações de Circuit Breaker.
    
    Representa erros que ocorrem durante operações protegidas por circuit breaker,
    incluindo rejeições devido ao circuito aberto e falhas na execução.
    
    Attributes:
        service_name: Nome do serviço associado ao circuit breaker.
        circuit_state: Estado do circuit breaker no momento do erro.
    """
    service_name: Optional[str] = None
    circuit_state: Optional[str] = None

@dataclass
class APIError(ErrorModel):
    """Modelo de erro específico para erros da API.
    
    Representa erros que ocorrem durante interações com a API,
    como autenticação, autorização, formato de dados, etc.
    
    Attributes:
        message: Mensagem de erro legível para humanos.
        endpoint: Endpoint da API que gerou o erro.
        request_id: Identificador único da requisição.
        method: Método HTTP da requisição (GET, POST, etc).
        resource: Recurso da API que foi acessado.
    """
    endpoint: Optional[str] = None
    request_id: Optional[str] = None
    method: Optional[str] = None
    resource: Optional[str] = None
    
@dataclass
class ComparisonError(ErrorModel):
    """Modelo de erro específico para operações de comparação.
    
    Representa erros que ocorrem durante a comparação de dados entre
    instrutor e alunos.
    
    Attributes:
        message: Mensagem de erro legível para humanos.
        comparison_id: Identificador único da operação de comparação.
        instructor_id: Identificador do instrutor envolvido na comparação.
        student_id: Identificador do aluno envolvido no erro (se aplicável).
        ai_model: Nome do modelo de IA utilizado (se aplicável).
        phase: Fase da comparação onde o erro ocorreu (ex: "validação", "processamento").
    """
    comparison_id: Optional[str] = None
    instructor_id: Optional[str] = None
    student_id: Optional[str] = None
    ai_model: Optional[str] = None
    phase: Optional[str] = None
