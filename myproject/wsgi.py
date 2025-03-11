"""Configuração WSGI do projeto.

Expõe o callable WSGI como uma variável de módulo chamada ``application``.
"""

import os
import logging
from django.core.wsgi import get_wsgi_application

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

try:
    application = get_wsgi_application()
    logger.info("Aplicação WSGI inicializada com sucesso")
except Exception as e:
    logger.error(f"Erro ao inicializar aplicação WSGI: {e}")
    raise
