"""
Tipos relacionados a métricas, monitoramento e logs do sistema.
"""
from typing import Dict, Optional, List, Tuple, TypedDict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from .base import JSONDict

# -----------------------------------------------------------------------------
# Tipos para Métricas e Monitoramento e Logs
# -----------------------------------------------------------------------------
HTTP_METHODS = [
    ('GET', 'GET'),
    ('POST', 'POST'),
    ('PUT', 'PUT'),
    ('PATCH', 'PATCH'),
    ('DELETE', 'DELETE'),
]
"""Métodos HTTP suportados pela API."""

class UsageMetrics(JSONDict):
    """Métricas de uso para um token específico.
    
    Rastreia estatísticas importantes como número total de chamadas,
    tempo médio de resposta e distribuição de códigos de status HTTP.
    Utilizado para análise de uso da API e monitoramento de performance.
    
    Attributes:
        name: Nome descritivo do token para identificação fácil.
        total_calls: Número total de chamadas de API realizadas com este token.
        avg_time: Tempo médio de resposta em milissegundos.
        status_codes: Mapeamento de códigos de status HTTP para quantidade de ocorrências.
    """
    name: str
    total_calls: int
    avg_time: float
    status_codes: Dict[int, int]

TokenMetrics = Dict[str, UsageMetrics]
"""
Mapeamento de IDs de tokens para suas respectivas métricas de uso.
Geralmente usado para agregar dados de uso da API por token,
facilitando o rastreamento e geração de relatórios de utilização.
"""

@dataclass
class APILog:
    """Dados de log da API.
    
    Args:
        id: Identificador do log.
        user_token: Token do usuário.
        request_method: Método da requisição.
        request_path: Caminho solicitado.
        request_body: Corpo enviado.
        response_body: Corpo de resposta.
        status_code: Código de status HTTP.
        execution_time: Tempo de execução em segundos.
        requester_ip: IP do requisitante.
        timestamp: Momento da requisição.
    """
    id: int
    user_token: Optional[str]
    request_method: str
    request_path: str 
    request_body: Optional[str]
    response_body: Optional[str]
    status_code: int
    execution_time: float
    requester_ip: str
    timestamp: datetime

class DocumentType(Enum):
    """Tipos de documento suportados.
    
    Valores:
        PDF: Documento no formato PDF.
        DOCX: Documento no formato Microsoft Word.
        TXT: Documento de texto simples.
        JSON: Documento no formato JSON.
        JSONL: Documento em formato JSON Lines (uma entrada por linha).
    """
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    JSON = "json"
    JSONL = "jsonl"
