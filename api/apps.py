from django.apps import AppConfig

class ApiConfig(AppConfig):
    """Configuração da aplicação API.

    Atributos:
        default_auto_field (str): Tipo de campo automático padrão.
        name (str): Nome da aplicação.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
