"""Configurações do aplicativo ai_config.

Define a configuração básica para a aplicação Django.
"""

from django.apps import AppConfig

class AiConfigConfig(AppConfig):
    """Configuração do aplicativo de IA.

    Atributos:
        default_auto_field (str): Tipo do campo autoincremental.
        name (str): Nome do aplicativo.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_config'
