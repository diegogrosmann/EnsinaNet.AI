from django.apps import AppConfig

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        """Realiza configurações de inicialização ao registrar os signals.
        
        Retorna:
            None
        """
        import accounts.signals
