from datetime import datetime
from typing import Optional
from core.types.base import DataModel, DataModelDict
from dataclasses import dataclass

@dataclass
class APIFile(DataModel):
    """Representa um arquivo na API."""
    id: str
    filename: str
    bytes: int
    created_at: Optional[datetime] = None

@dataclass
class APIFileCollection(DataModelDict[APIFile]):
    """Coleção de arquivos na API."""
    pass


@dataclass
class APIModel:
    """Representa um modelo na API."""
    id: str
    name: str
    is_fine_tuned: bool

@dataclass
class APIModelCollection(DataModelDict[APIModel]):
    """Coleção de modelos na API."""
    pass
