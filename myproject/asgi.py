"""Configuração ASGI do projeto.

Expõe o callable ASGI como uma variável de módulo chamada ``application``.
"""

import os
import logging
from django.core.asgi import get_asgi_application

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

try:
    application = get_asgi_application()
    logger.info("Aplicação ASGI inicializada com sucesso")
except Exception as e:
    logger.error(f"Erro ao inicializar aplicação ASGI: {e}")
    raise
