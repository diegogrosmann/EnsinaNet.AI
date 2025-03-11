"""Configurações do aplicativo ai_config.

Define a configuração básica para a aplicação Django.
"""

import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class AiConfigConfig(AppConfig):
    """Configuração do aplicativo de IA.

    Atributos:
        default_auto_field (str): Tipo do campo autoincremental.
        name (str): Nome do aplicativo.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_config'
    
    def ready(self):
        """Executa código quando a aplicação é inicializada.
        
        Este método é chamado pelo Django quando a aplicação está pronta,
        permitindo executar código de inicialização necessário.
        """
        logger.info("Aplicação ai_config inicializada com sucesso")
        
        # Importando sinais se necessário
        try:
            # import ai_config.signals
            pass  # Futuramente, sinais podem ser importados aqui
        except ImportError as e:
            logger.error(f"Erro ao importar sinais da aplicação ai_config: {e}")
