# ai_config/storage.py

from django.core.files.storage import FileSystemStorage
import os

class OverwriteStorage(FileSystemStorage):
    """Subclasse de FileSystemStorage que sobrescreve arquivos existentes.

    Este armazenamento remove o arquivo existente se o nome já estiver em uso.

    Methods:
        get_available_name: Retorna o mesmo nome removendo o arquivo pré-existente.
    """

    def get_available_name(self, name, max_length=None):
        """Retorna o nome disponível para o arquivo, removendo o arquivo existente se necessário.

        Args:
            name (str): Nome original do arquivo.
            max_length (int, optional): Comprimento máximo permitido para o nome.

        Returns:
            str: Nome disponível para armazenamento.
        """
        if self.exists(name):
            self.delete(name)
        return name
