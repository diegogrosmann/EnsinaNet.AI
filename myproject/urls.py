"""URLs principais do projeto.

Define as rotas principais e inclui as URLs dos aplicativos.
"""

import logging
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls.resolvers import URLPattern, URLResolver
from typing import List, Union
from accounts.views import CustomConfirmEmailView

logger = logging.getLogger(__name__)

urlpatterns: List[Union[URLPattern, URLResolver]] = [
    # Sistema e Administração
    path('admin/', admin.site.urls),
    path('markdownx/', include('markdownx.urls')),
    
    # Confirmação de Email
    path('accounts/confirm-email/<str:key>/', 
         CustomConfirmEmailView.as_view(), 
         name='account_confirm_email'),
    
    # Aplicações Core
    path('', include('public.urls', namespace='public')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    
    # APIs e Configurações
    path('api/', include('api.urls', namespace='api')),
    path('ai-config/', include('ai_config.urls', namespace='ai_config')),
]

# Configurações para modo DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

logger.info("URLs principais do projeto carregadas")
