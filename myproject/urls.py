"""URLs principais do projeto.

Define as rotas principais e inclui as URLs dos demais aplicativos.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from accounts.views import CustomConfirmEmailView

urlpatterns = [
    # Sistema e Administração
    path('admin/', admin.site.urls),
    path('markdownx/', include('markdownx.urls')),
    
    # Confirmação de Email
    path('accounts/confirm-email/<str:key>/', CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    
    # Aplicações Core
    path('', include('public.urls', namespace='public')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    
    # APIs e Configurações
    path('api/', include('api.urls', namespace='api')),
    path('ai-config/', include('ai_config.urls', namespace='ai_config')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
