"""Configuração Celery do projeto.

Define configuração básica do Celery e suas tasks periódicas.
"""

from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery
from django.conf import settings

logger = logging.getLogger(__name__)

# Configuração de debug condicional
if os.getenv('CELERY_DEBUG', 'False').lower() in ('true', '1'):
    try:
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        logger.info("Celery worker aguardando debugger na porta 5678...")
        debugpy.wait_for_client()
        logger.info("Debugger conectado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao configurar debugger: {e}")

# Configuração do Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

try:
    app = Celery('myproject')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
    
    # Tasks periódicas
    app.conf.beat_schedule = {
        'update-training-status': {
            'task': 'ai_config.tasks.update_training_status',
            'schedule': 60.0,
        },
    }
    
    logger.info("Celery configurado com sucesso")
except Exception as e:
    logger.error(f"Erro ao configurar Celery: {e}")
    raise

@app.task(bind=True)
def debug_task(self):
    """Task para debug do Celery."""
    logger.debug(f'Request: {self.request!r}')
