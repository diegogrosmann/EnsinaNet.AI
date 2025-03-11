from __future__ import absolute_import, unicode_literals
import os

if os.getenv('CELERY_DEBUG', 'False').lower() in ('true', '1'):
    import debugpy
    # Abre a porta 5678 para o debugger
    debugpy.listen(("0.0.0.0", 5678))
    print("Celery worker aguardando o attach do debugger na porta 5678...")
    # Opcional: pausa até o debugger se conectar
    debugpy.wait_for_client()
    print("Conexão bem sucedida")

from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

app.conf.beat_schedule = {
    'update-training-status': {
        'task': 'ai_config.tasks.update_training_status',
        'schedule': 60.0,
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
