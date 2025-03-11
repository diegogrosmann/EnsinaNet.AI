"""Configuração da aplicação API.

Define configurações básicas e inicialização da aplicação API.
"""

import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class ApiConfig(AppConfig):
    """Configuração da aplicação API.

    Attributes:
        default_auto_field (str): Tipo de campo autoincremental.
        name (str): Nome da aplicação.
        verbose_name (str): Nome amigável da aplicação.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'API'
    
    def ready(self) -> None:
        """Executa código de inicialização da aplicação.
        
        Configura signals, registra clientes de IA e inicializa componentes.
        """
        try:
            # Importa módulos necessários
            import api.signals
            import api.utils.clientsIA
            logger.info("Aplicação API inicializada com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar aplicação API: {e}")
