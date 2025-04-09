"""Storage customizado para gerenciar arquivos de treinamento.

Este módulo fornece uma implementação personalizada do FileSystemStorage
que permite sobrescrever arquivos existentes automaticamente.
"""

import logging
from django.core.files.storage import FileSystemStorage
import os

logger = logging.getLogger(__name__)

class OverwriteStorage(FileSystemStorage):
    """Storage que sobrescreve arquivos existentes automaticamente.
    
    Esta classe estende FileSystemStorage para remover arquivos existentes
    quando um novo arquivo com o mesmo nome é enviado, evitando duplicatas.
    """

    def get_available_name(self, name: str, max_length: int = None) -> str:
        """Retorna o nome do arquivo, removendo qualquer arquivo existente.
        
        Args:
            name: Nome original do arquivo.
            max_length: Comprimento máximo permitido para o nome (opcional).
            
        Returns:
            str: Nome do arquivo para armazenamento.
        """
        try:
            if self.exists(name):
                logger.debug(f"Removendo arquivo existente: {name}")
                self.delete(name)
            return name
        except Exception as e:
            logger.error(f"Erro ao processar nome de arquivo '{name}': {e}")
            raise
