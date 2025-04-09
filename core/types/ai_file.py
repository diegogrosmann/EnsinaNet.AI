from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Type, Union, IO
import json
import os
import logging
from io import BytesIO

from core.types.ai import AIExampleDict
from core.types.base import BaseModel, DataModelDict


@dataclass
class AIFile(BaseModel, ABC):
    """Dados de arquivo de treinamento.
    
    Representa um arquivo de dados de treinamento enviado pelo usuário
    e seus metadados associados.
    
    Args:
        user_id: Identificador do usuário proprietário.
        name: Nome do arquivo.
        id: Identificador único do arquivo (opcional).
        uploaded_at: Data de envio do arquivo.
        file: Coleção de exemplos de treinamento.
        file_size: Tamanho do arquivo em bytes.
        example_count: Quantidade de exemplos no arquivo.
    """
    user_id: int
    name: str
    data: Optional[AIExampleDict] = None
    id: Optional[int] = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    file_size: Optional[int] = 0
    example_count: Optional[int] = 0

class AIFileDict(DataModelDict[AIFile]):
    """Dicionário tipo-seguro para arquivos de IA.
    Estrutura:
        "file_id" = AIFile
    """
    
    