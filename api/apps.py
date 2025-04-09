"""Configuração da aplicação API.

Define configurações básicas e inicialização da aplicação API,
incluindo a configuração de componentes que precisam ser carregados
durante a inicialização do Django.
"""

import logging
import sys
from django.apps import AppConfig
from api.exceptions import APIClientException
from django.conf import settings

logger = logging.getLogger(__name__)

class ApiConfig(AppConfig):
    """Configuração da aplicação API.

    Esta classe controla a inicialização da aplicação API,
    carregando componentes necessários e configurando
    os serviços utilizados.

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
        
        Este método é chamado automaticamente pelo Django quando a aplicação
        é carregada. Configura sinais, registra clientes de IA e 
        inicializa outros componentes necessários.
        
        Raises:
            ApplicationError: Se ocorrer erro crítico durante a inicialização.
        """
        # Evitar execução duplicada durante reload do servidor em desenvolvimento
        if 'runserver' in sys.argv and not sys.argv[0].endswith('manage.py'):
            return
            
        try:
            logger.info("Iniciando aplicação API...")
            
            # Importa módulos necessários
            import api.signals
            logger.debug("Módulo de sinais carregado")
            
            # Inicializa clientes de IA
            self._initialize_ai_clients()
            
            # Configura middlewares e outros componentes
            self._setup_components()
            
            logger.info("Aplicação API inicializada com sucesso")
        except Exception as e:
            logger.error(f"Erro crítico ao inicializar aplicação API: {str(e)}", exc_info=True)
            # Em produção, não queremos que um erro impeça o servidor de iniciar
            # então apenas logamos o erro em vez de propagar a exceção
            if not settings.DEBUG:
                logger.error("API pode estar parcialmente funcional devido a erro de inicialização")
            else:
                raise APIClientException(f"Falha na inicialização da API: {str(e)}")
    
    def _initialize_ai_clients(self) -> None:
        """Inicializa e configura clientes de IA.
        
        Carrega configurações de clientes de IA a partir do banco de dados
        ou arquivos de configuração, e prepara os clientes para uso.
        """
        try:
            import api.utils.clientsIA
            logger.info("Clientes de IA inicializados com sucesso")
        except ImportError as e:
            logger.warning(f"Módulo de clientes de IA não disponível: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao inicializar clientes de IA: {str(e)}", exc_info=True)
    
    def _setup_components(self) -> None:
        """Configura componentes adicionais da API.
        
        Prepara middlewares, interceptadores, validadores e outros
        componentes utilizados pela API.
        """
        logger.debug("Configurando componentes da API")
        # Código para configurar componentes adicionais
        # ...
        
        # Caso necessário, podem ser adicionadas outras inicializações aqui
        self.configure_rest_framework()

    def configure_rest_framework(self):
        """Configura o REST Framework."""
        settings.REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': (
                'accounts.authentication.CustomTokenAuthentication',
            ),
            'DEFAULT_PERMISSION_CLASSES': (
                'rest_framework.permissions.IsAuthenticated',
            ),
            'EXCEPTION_HANDLER': 'api.exception_handlers.custom_exception_handler',
            'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
            'DEFAULT_VERSION': 'v1',
            'ALLOWED_VERSIONS': ['v1'],  # Defina aqui todas as versões que sua API suportará
        }
        logger.info("Configurações do REST Framework carregadas")
