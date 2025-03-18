"""Configuração de URLs do aplicativo ai_config.

Define os padrões de URL para:
- Gerenciamento de IAs
- Treinamentos e captura
- Configuração de tokens
"""

import logging
from django.urls import path, include
from ai_config import views

logger = logging.getLogger(__name__)

app_name = 'ai_config'

# Padrões para gerenciamento de IAs
ai_patterns = [
    path('', views.manage_ai, name='ai_manage'),
    path('create/', views.create_ai, name='ai_create'),
    path('<int:ai_id>/', include([
        path('edit/', views.edit_ai, name='ai_edit'),
        path('delete/', views.delete_ai, name='ai_delete'),
        path('available-tokens/', views.ai_available_tokens, name='ai_available_tokens'),
    ])),
    # Nova URL para listar modelos de um cliente IA
    path('client/<int:ai_client_id>/models/', views.get_ai_models, name='ai_client_models'),
]

# Padrões para treinamento e captura
training_patterns = [
    path('', views.training_center, name='training_center'),
    path('files/', include([
        path('', views.training_file_form, name='training_file_create'),
        path('upload/', views.training_file_upload, name='training_file_upload'),
        path('<int:file_id>/', include([
            path('', views.training_file_form, name='training_file_edit'),
            path('download/', views.training_file_download, name='training_file_download'),
            path('delete/', views.training_file_delete, name='training_file_delete'),
        ])),
    ])),
    path('capture/toggle/', views.capture_toggle, name='capture_toggle'),
    path('tokens/<uuid:token_id>/ai/<int:ai_id>/get-examples', 
         views.capture_get_examples, name='capture_get_examples'),
    path('train/', include([
        path('', views.training_ai, name='training_ai'),
        path('<int:training_id>/' , include([
            path('cancel/', views.training_cancel, name='training_cancel'),
            path('delete/', views.training_delete, name='training_delete'),
        ])),
    ])),
    path('monitor/', views.training_monitor, name='training_monitor'), 
]

# Padrões para configuração de tokens
token_patterns = [
    path('<uuid:token_id>/', include([
        path('prompt', views.prompt_config, name='token_prompt_config'),
        path('ai_link', views.token_ai_link, name='token_ai_link'),
    ])),
    path('bulk_toggle/', views.token_ai_toggle, name='token_ai_toggle'),
]

# URLs principais do aplicativo
urlpatterns = [ 
    path('ai/', include(ai_patterns)),
    path('training/', include(training_patterns)),
    path('token/', include(token_patterns)),
]

logger.debug("URLs do aplicativo ai_config carregadas")