"""
Tipos relacionados a métricas, monitoramento e logs do sistema.

Define estruturas de dados para representar métricas de uso,
logs de API e tipos de documentos para análise e monitoramento.
"""
import logging
from typing import Dict, Optional, List, Tuple, TypedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from .base import JSONDict
from core.exceptions import APIError

logger = logging.getLogger(__name__)

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
"""
Métodos HTTP suportados pela API.
Cada tupla contém (valor técnico, valor de exibição).
"""

class UsageMetrics(TypedDict):
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
    
    Registra detalhes completos de uma requisição à API para fins de 
    auditoria, depuração e análise de uso.
    
    Args:
        id: Identificador único do registro de log.
        user_token: Token do usuário que fez a requisição.
        request_method: Método HTTP da requisição (GET, POST, etc.).
        request_path: Caminho da URL solicitada.
        request_body: Corpo da requisição (se houver).
        response_body: Corpo da resposta (se houver).
        status_code: Código de status HTTP da resposta.
        execution_time: Tempo de execução da requisição em segundos.
        requester_ip: Endereço IP do requisitante.
        timestamp: Momento exato da requisição.
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
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        if not self.request_method in [m[0] for m in HTTP_METHODS]:
            logger.warning(f"Log criado com método HTTP desconhecido: {self.request_method}")
            
        log_level = logging.INFO if 200 <= self.status_code < 400 else logging.WARNING
        logger.log(log_level, f"APILog: {self.request_method} {self.request_path} "
                        f"→ {self.status_code} em {self.execution_time:.3f}s")
    
    def to_dict(self) -> JSONDict:
        """Converte o log para um dicionário.
        
        Returns:
            Dicionário com os dados do log formatados.
        """
        logger.debug(f"Convertendo APILog {self.id} para dicionário")
        return {
            "id": self.id,
            "user_token": self.user_token,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "status_code": self.status_code,
            "execution_time": self.execution_time,
            "requester_ip": self.requester_ip,
            "timestamp": self.timestamp.isoformat(),
            # Corpos de requisição e resposta podem ser muito grandes
            # e geralmente são incluídos apenas sob demanda
        }
    
    @classmethod
    def create(cls, **kwargs) -> 'APILog':
        """Cria um novo registro de log com validações.
        
        Args:
            **kwargs: Parâmetros para inicialização do log.
            
        Returns:
            Nova instância de APILog.
            
        Raises:
            ValueError: Se parâmetros obrigatórios estiverem ausentes.
        """
        required = ['request_method', 'request_path', 'status_code', 'execution_time', 'requester_ip']
        missing = [f for f in required if f not in kwargs]
        
        if missing:
            logger.error(f"Tentativa de criar APILog sem campos obrigatórios: {', '.join(missing)}")
            raise ValueError(f"Campos obrigatórios ausentes: {', '.join(missing)}")
            
        if 'timestamp' not in kwargs:
            kwargs['timestamp'] = datetime.now()
            
        return cls(**kwargs)

class DocumentType(Enum):
    """Tipos de documento suportados.
    
    Representa os formatos de documento que o sistema pode processar,
    com valores padronizados para uso consistente em toda a aplicação.
    
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
    
    def get_mime_type(self) -> str:
        """Retorna o tipo MIME correspondente ao formato do documento.
        
        Returns:
            str: Tipo MIME do formato do documento.
        """
        mime_types = {
            self.PDF: "application/pdf",
            self.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            self.TXT: "text/plain",
            self.JSON: "application/json",
            self.JSONL: "application/jsonl"
        }
        return mime_types.get(self, "application/octet-stream")
    
    @classmethod
    def from_extension(cls, extension: str) -> Optional['DocumentType']:
        """Determina o tipo de documento baseado na extensão do arquivo.
        
        Args:
            extension: Extensão do arquivo (sem o ponto).
            
        Returns:
            DocumentType correspondente ou None se não reconhecido.
        """
        try:
            return cls(extension.lower())
        except ValueError:
            logger.warning(f"Extensão de arquivo não reconhecida: {extension}")
            return None