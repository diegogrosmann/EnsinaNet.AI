from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

# Define o módulo padrão de configuração do Django para o Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')

# Lê a configuração do Django e a aplica ao Celery
# - namespace='CELERY' significa que todas as chaves de configuração relacionadas ao celery devem ter um prefixo CELERY_.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descobre e carrega tasks definidas em todos os apps do Django
# Celery autodiscover_tasks: Procura por tasks.py em todos os apps Django registrados.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Adiciona a task periódica
app.conf.beat_schedule = {
    'update-training-status': {
        'task': 'ai_config.tasks.update_training_status',
        'schedule': 60.0,  # a cada 60 segundos
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
