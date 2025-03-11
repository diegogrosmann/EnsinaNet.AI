"""URLs do aplicativo public.

Define as rotas públicas da aplicação, acessíveis sem autenticação.
"""

import logging
from django.urls import path
from django.urls.resolvers import URLPattern
from typing import List
from . import views

logger = logging.getLogger(__name__)

app_name = 'public'

urlpatterns: List[URLPattern] = [
    path('', views.index, name='index'),
]

logger.debug(f"{len(urlpatterns)} rotas públicas registradas")
