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

<<<<<<< HEAD
urlpatterns: List[URLPattern] = [
=======
urlpatterns = [
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
    path('', views.index, name='index'),
]

logger.debug(f"{len(urlpatterns)} rotas públicas registradas")
