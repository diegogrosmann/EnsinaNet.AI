"""Configuração do aplicativo public.

Este módulo define a configuração básica do aplicativo público
que serve páginas e recursos acessíveis sem autenticação.
"""

import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class PublicConfig(AppConfig):
    """Configuração do aplicativo público.
    
    Attributes:
        default_auto_field: Tipo do campo autoincremental.
        name: Nome do aplicativo.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'public'
    
    def ready(self):
        """Executa código de inicialização do aplicativo."""
        logger.info("Aplicativo public inicializado")
