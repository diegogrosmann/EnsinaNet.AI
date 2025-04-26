"""URLs principais do projeto.

<<<<<<< HEAD
Define as rotas principais e inclui as URLs dos aplicativos.
"""

import logging
=======
Define as rotas principais e inclui as URLs dos demais aplicativos.
"""
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
<<<<<<< HEAD
from django.urls.resolvers import URLPattern, URLResolver
from typing import List, Union
from accounts.views import CustomConfirmEmailView

logger = logging.getLogger(__name__)

urlpatterns: List[Union[URLPattern, URLResolver]] = [
=======

from accounts.views import CustomConfirmEmailView

urlpatterns = [
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
    # Sistema e Administração
    path('admin/', admin.site.urls),
    path('markdownx/', include('markdownx.urls')),
    
    # Confirmação de Email
<<<<<<< HEAD
    path('accounts/confirm-email/<str:key>/', 
         CustomConfirmEmailView.as_view(), 
         name='account_confirm_email'),
=======
    path('accounts/confirm-email/<str:key>/', CustomConfirmEmailView.as_view(), name='account_confirm_email'),
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
    
    # Aplicações Core
    path('', include('public.urls', namespace='public')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    
    # APIs e Configurações
    path('api/', include('api.urls', namespace='api')),
    path('ai-config/', include('ai_config.urls', namespace='ai_config')),
<<<<<<< HEAD
    
    # Versão do Cliente
    path('client-version/', include('client_version.urls', namespace='client_version')),
    # Rota específica para a versão do cliente pnet
    path('install/pnet/', include('client_version.urls')),
=======
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
]

# Configurações para modo DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
<<<<<<< HEAD

logger.info("URLs principais do projeto carregadas")
=======
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
