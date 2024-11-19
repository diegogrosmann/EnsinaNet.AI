# ai_config/storage.py

from django.core.files.storage import FileSystemStorage
import os

class OverwriteStorage(FileSystemStorage):
    """
    Subclasse de FileSystemStorage que sobrescreve arquivos existentes com o mesmo nome.
    """
    def get_available_name(self, name, max_length=None):
        """
        Se o nome do arquivo já existir, o remove antes de retornar o nome.
        """
        if self.exists(name):
            self.delete(name)
        return name
