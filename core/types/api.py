"""
Tipos relacionados à API e integração com serviços externos.
"""
from typing import List
from dataclasses import dataclass
from datetime import datetime

# -----------------------------------------------------------------------------
# Tipos para API
# -----------------------------------------------------------------------------
@dataclass
class APIFile:
    """Dados de arquivo de treinamento.
    
    Args:
        id: Identificador do arquivo.
        filename: Nome do arquivo.
        bytes: Tamanho do arquivo em bytes.
        created_at: Data de criação do arquivo.
    """
    id: str
    filename: str
    bytes: int
    created_at: datetime

APIFileCollection = List[APIFile]

@dataclass
class APIModel:
    """Modelo de IA disponível para uso na API.
    
    Args:
        id: Identificador único do modelo.
        name: Nome do modelo.
        is_fine_tuned: Indica se é um modelo fine-tuned.
    """
    id: str
    name: str
    is_fine_tuned: bool

APIModelCollection = List[APIModel]
