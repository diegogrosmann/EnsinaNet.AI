from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class MyappConfig(AppConfig):
    """Configuração da aplicação Accounts.

    Define parâmetros básicos da aplicação de contas de usuário.

    Attributes:
        default_auto_field (str): Tipo de campo de chave primária automática.
        name (str): Nome da aplicação.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        """Inicializa a aplicação configurando signals e dependências.

        Este método é chamado quando a aplicação é inicializada e importa os signals
        para garantir seu registro correto.

        Returns:
            None
        """
        try:
            import accounts.signals
        except ImportError as e:
            logger.error(f"Erro ao importar os signals da aplicação accounts: {str(e)}", exc_info=True)
