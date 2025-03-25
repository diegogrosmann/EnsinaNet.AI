"""Configuração do Celery do projeto.

Este módulo define a configuração básica do Celery, a descoberta automática de tasks e a
definição de tasks periódicas. Além disso, configura o debug do worker se necessário.
"""

from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery
from django.conf import settings

logger = logging.getLogger(__name__)

# Configuração condicional do debugger (debugpy)
if os.getenv('CELERY_DEBUG', 'False').lower() in ('true', '1'):
    try:
        import debugpy
        # Inicia o debugpy para ouvir na porta 5678 em todas as interfaces
        debugpy.listen(("0.0.0.0", 5678))
        logger.info("Celery worker aguardando debugger na porta 5678...")
        # Aguarda a conexão do debugger
        debugpy.wait_for_client()
        logger.info("Debugger conectado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao configurar debugger: {e}", exc_info=True)

# Define a variável de ambiente para as configurações do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

try:
    # Criação da instância do Celery para o projeto
    app = Celery('myproject')
    # Carrega as configurações do Django com o prefixo "CELERY_"
    app.config_from_object('django.conf:settings', namespace='CELERY')
    # Descobre automaticamente as tasks registradas nos apps instalados
    app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
    
    # Configuração das tasks periódicas (beat schedule)
    app.conf.beat_schedule = {
        'update-training-status': {
            'task': 'ai_config.tasks.update_training_status',
            'schedule': 60.0,
        },
    }
    
    logger.info("Celery configurado com sucesso")
except Exception as e:
    logger.error(f"Erro ao configurar Celery: {e}", exc_info=True)
    raise

@app.task(bind=True)
def debug_task(self):
    """Task para debug do Celery.

    Esta task pode ser utilizada para verificar se o worker está recebendo requisições,
    registrando informações da requisição atual.
    """
    logger.debug(f'Request: {self.request!r}')
