from django.apps import AppConfig
import logging
from django.conf import settings 

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

        # Configurações específicas do app
        self.configure_app()

    def configure_app(self):
        """Configura as variáveis específicas do aplicativo."""
        # Define as URLs de redirecionamento
        settings.LOGIN_REDIRECT_URL = 'accounts:tokens'
        settings.LOGOUT_REDIRECT_URL = 'accounts:login'
        settings.LOGIN_URL = 'accounts:login'
        settings.LOGOUT_URL = 'accounts:logout'

        # URLs de redirecionamento após confirmação de email
        settings.ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = 'accounts:login'
        settings.ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = 'accounts:login'

        logger.info("Configurações do app accounts carregadas")
