"""URLs para API v1.

Define os endpoints disponíveis na versão 1 da API.
"""

import logging
from django.urls import path
from . import views

logger = logging.getLogger(__name__)

app_name = 'v1'

urlpatterns = [
    path('compare/', views.compare, name='compare'),
]

logger.debug("URLs da API v1 carregadas")
