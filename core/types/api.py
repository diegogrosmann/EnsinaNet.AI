"""
Tipos relacionados à API e integração com serviços externos.

Define estruturas de dados para representar objetos comuns usados
nas integrações com APIs e serviços externos.
"""
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from core.exceptions import APIError

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Tipos para API
# -----------------------------------------------------------------------------
@dataclass
class APIFile:
    """Dados de arquivo de treinamento.
    
    Representa um arquivo disponível em uma API externa,
    contendo metadados relevantes como tamanho e data de criação.
    
    Args:
        id: Identificador único do arquivo.
        filename: Nome do arquivo.
        bytes: Tamanho do arquivo em bytes.
        created_at: Data de criação do arquivo.
    """
    id: str
    filename: str
    bytes: int
    created_at: datetime
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        logger.debug(f"APIFile inicializado: {self.filename} ({self.bytes} bytes)")
    
    @classmethod
    def from_dict(cls, data: dict) -> 'APIFile':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com dados do arquivo.
            
        Returns:
            APIFile: Instância criada com os dados fornecidos.
            
        Raises:
            APIError: Se os dados estiverem incompletos ou inválidos.
        """
        try:
            # Converter string de data para objeto datetime se necessário
            created_at = data.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            elif created_at is None:
                created_at = datetime.now()
                
            return cls(
                id=data['id'],
                filename=data['filename'],
                bytes=int(data['bytes']),
                created_at=created_at
            )
        except KeyError as e:
            logger.error(f"Campo obrigatório ausente ao criar APIFile: {e}")
            raise APIError(f"Dados de arquivo incompletos: campo {e} ausente")
        except ValueError as e:
            logger.error(f"Erro ao converter dados para APIFile: {e}")
            raise APIError(f"Erro nos dados do arquivo: {e}")

APIFileCollection = List[APIFile]
"""Coleção de arquivos disponíveis em uma API externa."""

@dataclass
class APIModel:
    """Modelo de IA disponível para uso na API.
    
    Representa um modelo de IA que pode ser utilizado para
    inferência ou fine-tuning através da API.
    
    Args:
        id: Identificador único do modelo.
        name: Nome descritivo do modelo.
        is_fine_tuned: Indica se é um modelo com ajuste fino (fine-tuned).
        created_at: Data de criação do modelo (opcional).
        owner: Proprietário do modelo (opcional).
    """
    id: str
    name: str
    is_fine_tuned: bool
    created_at: Optional[datetime] = None
    owner: Optional[str] = None
    
    def __post_init__(self):
        """Valida e registra a criação do objeto."""
        logger.debug(f"APIModel inicializado: {self.name} (fine-tuned: {self.is_fine_tuned})")
    
    @classmethod
    def from_dict(cls, data: dict) -> 'APIModel':
        """Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com dados do modelo.
            
        Returns:
            APIModel: Instância criada com os dados fornecidos.
            
        Raises:
            APIError: Se os dados estiverem incompletos ou inválidos.
        """
        try:
            # Converter string de data para objeto datetime se necessário
            created_at = data.get('created_at')
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                
            return cls(
                id=data['id'],
                name=data['name'],
                is_fine_tuned=bool(data.get('is_fine_tuned', False)),
                created_at=created_at,
                owner=data.get('owner')
            )
        except KeyError as e:
            logger.error(f"Campo obrigatório ausente ao criar APIModel: {e}")
            raise APIError(f"Dados de modelo incompletos: campo {e} ausente")

APIModelCollection = List[APIModel]
"""Coleção de modelos disponíveis em uma API externa."""