"""
Tipos relacionados a tarefas assíncronas e processamento em segundo plano.

Define estruturas de dados para representar tarefas que são processadas
de forma assíncrona, permitindo operações de longa duração.
"""
import logging
import uuid
import json
from typing import Dict, Optional, Any, Union, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .base import JSONDict
from core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para processamento assíncrono
# -----------------------------------------------------------------------------
class AsyncTaskStatus(Enum):
    """Status de uma tarefa assíncrona.
    
    Representa os possíveis estados de uma tarefa em processamento assíncrono,
    permitindo rastrear seu progresso desde a criação até a conclusão.
    
    Valores:
        PENDING: Tarefa foi criada mas não iniciou o processamento.
        PROCESSING: Tarefa está sendo processada no momento.
        COMPLETED: Tarefa foi concluída com sucesso.
        FAILED: Tarefa falhou durante o processamento.
        EXPIRED: Tarefa expirou sem ser processada ou consultada.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    
    def __str__(self) -> str:
        """Representação em string do status.
        
        Returns:
            str: Nome do status em formato legível.
        """
        return self.value

T = TypeVar('T')

@dataclass
class AsyncTask(Generic[T]):
    """Tarefa assíncrona genérica.
    
    Representa uma tarefa que será processada de forma assíncrona,
    contendo identificador único, status, dados de entrada e resultado.
    
    Args:
        task_id: Identificador único da tarefa.
        status: Status atual da tarefa.
        created_at: Data e hora de criação da tarefa.
        updated_at: Data e hora da última atualização do status.
        input_data: Dados de entrada para a tarefa.
        result: Resultado da tarefa (quando concluída).
        error: Mensagem de erro (quando falha).
        user_id: ID do usuário que criou a tarefa.
        user_token_id: ID do token usado para criar a tarefa.
        expiration: Data e hora de expiração da tarefa.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: AsyncTaskStatus = AsyncTaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    input_data: Optional[Any] = None
    result: Optional[T] = None
    error: Optional[str] = None
    user_id: Optional[int] = None
    user_token_id: Optional[int] = None
    expiration: Optional[datetime] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        logger.debug(f"AsyncTask {self.task_id} criada com status {self.status}")
    
    def update_status(self, new_status: AsyncTaskStatus, error_msg: Optional[str] = None) -> None:
        """Atualiza o status da tarefa.
        
        Args:
            new_status: Novo status da tarefa.
            error_msg: Mensagem de erro (se aplicável).
        """
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now()
        
        if new_status == AsyncTaskStatus.FAILED and error_msg:
            self.error = error_msg
            
        logger.info(f"AsyncTask {self.task_id} atualizada: {old_status} -> {new_status}")
    
    def set_result(self, result: T) -> None:
        """Define o resultado da tarefa e marca como concluída.
        
        Args:
            result: Resultado da tarefa.
        """
        self.result = result
        self.update_status(AsyncTaskStatus.COMPLETED)
        logger.info(f"AsyncTask {self.task_id} concluída com sucesso")
    
    def set_failure(self, error_msg: str) -> None:
        """Marca a tarefa como falha com uma mensagem de erro.
        
        Args:
            error_msg: Descrição do erro ocorrido.
        """
        self.update_status(AsyncTaskStatus.FAILED, error_msg)
        logger.error(f"AsyncTask {self.task_id} falhou: {error_msg}")
    
    def to_dict(self) -> JSONDict:
        """Converte a tarefa para um dicionário serializável.
        
        Returns:
            JSONDict: Dicionário com os dados da tarefa.
        """
        result = {
            "task_id": self.task_id,
            "status": str(self.status),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
        if self.user_id:
            result["user_id"] = self.user_id
            
        if self.expiration:
            result["expiration"] = self.expiration.isoformat()
            
        if self.status == AsyncTaskStatus.COMPLETED and self.result is not None:
            result["result"] = self.result
            
        if self.status == AsyncTaskStatus.FAILED and self.error:
            result["error"] = self.error
            
        return result

@dataclass
class AsyncComparisonTask(AsyncTask[Dict[str, Any]]):
    """Tarefa assíncrona específica para comparações.
    
    Especializa AsyncTask para o caso específico de comparações,
    com métodos e propriedades específicas para este tipo de operação.
    
    Args:
        compare_data: Dados de entrada para a comparação.
    """
    compare_data: Optional[JSONDict] = None
    
    def __post_init__(self):
        """Inicializa dados específicos para comparações."""
        super().__post_init__()
        if self.compare_data:
            self.input_data = self.compare_data
            
        # Calcula estatísticas da tarefa
        if self.input_data and isinstance(self.input_data, dict):
            students_count = len(self.input_data.get("students", {}))
            logger.info(f"AsyncComparisonTask {self.task_id} criada com {students_count} alunos")
    
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
        if self.status == AsyncTaskStatus.COMPLETED and self.result:
            student_ids = list(self.result.get("students", {}).keys())
            ai_models = set()
            for student_data in self.result.get("students", {}).values():
                ai_models.update(student_data.keys())
            
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