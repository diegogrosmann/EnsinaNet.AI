"""Módulo para processamento de documentos.

Define classes e funções para manipulação e análise de documentos
em diversos formatos (PDF, Word, etc).
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from core.exceptions import FileProcessingError
from core.types.base import JSONDict

logger = logging.getLogger(__name__)

@dataclass
class DocumentMetadata:
    """Metadados de um documento processado.
    
    Armazena informações sobre o documento como nome, tamanho e formato.
    """
    filename: str
    size_bytes: int
    mime_type: str = ""
    page_count: Optional[int] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    author: Optional[str] = None
    
    def to_dict(self) -> JSONDict:
        """Converte os metadados para um dicionário.
        
        Returns:
            JSONDict: Dicionário com os metadados do documento.
        """
        return {k: v for k, v in self.__dict__.items() if v is not None}

@dataclass
class DocumentContent:
    """Conteúdo extraído de um documento.
    
    Armazena o texto extraído e outras informações estruturais do documento.
    """
    text: str
    metadata: DocumentMetadata
    sections: List[Dict[str, Any]] = None
    tables: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Inicializa listas vazias para campos opcionais."""
        if self.sections is None:
            self.sections = []
        if self.tables is None:
            self.tables = []
    
    def word_count(self) -> int:
        """Calcula o número de palavras no texto do documento.
        
        Returns:
            int: Número de palavras no documento.
        """
        return len(self.text.split())

def extract_metadata(file_data: Dict[str, Any]) -> DocumentMetadata:
    """Extrai metadados básicos de um documento.
    
    Args:
        file_data: Dicionário com informações do arquivo (nome e conteúdo base64).
        
    Returns:
        DocumentMetadata: Objeto com metadados do documento.
        
    Raises:
        FileProcessingError: Se ocorrer erro ao processar os metadados.
    """
    logger.debug(f"Extraindo metadados do arquivo: {file_data.get('name')}")
    
    try:
        import base64
        if 'name' not in file_data or 'content' not in file_data:
            raise FileProcessingError("Dados do arquivo incompletos: faltam campos obrigatórios")
            
        content_bytes = base64.b64decode(file_data['content'])
            
        # Calcular o tamanho em bytes do conteúdo decodificado
        try:
            size = len(content_bytes)
        except Exception as e:
            logger.error(f"Erro ao calcular tamanho do arquivo: {e}")
            size = 0
        
        # Determinar o tipo MIME básico baseado na extensão
        filename = file_data['name']
        mime_type = ""
        if filename.lower().endswith('.pdf'):
            mime_type = "application/pdf"
        elif filename.lower().endswith('.docx'):
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        return DocumentMetadata(
            filename=filename,
            size_bytes=size,
            mime_type=mime_type
        )
        
    except FileProcessingError:
        raise
    except Exception as e:
        logger.exception(f"Erro ao extrair metadados: {str(e)}")
        raise FileProcessingError(f"Erro ao processar metadados: {str(e)}")
