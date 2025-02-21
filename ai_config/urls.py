"""URLs do aplicativo ai_config."""
from django.urls import path, include
from ai_config import views

app_name = 'ai_config'

ai_configs_patterns = [
    path('', views.ai_config_manage, name='ai_config_manage'),
    path('create/', views.ai_config_create, name='ai_config_create'),
    path('<int:config_id>/', include([
        path('edit/', views.ai_config_edit, name='ai_config_edit'),
        path('delete/', views.ai_config_delete, name='ai_config_delete'),
        path('toggle/', views.ai_config_toggle, name='ai_config_toggle'),  # Nova URL
    ])),
]

ai_patterns = [
    path('configs/', include(ai_configs_patterns)),
    path('get/', views.get_token_ais, name='token_get_ais'),
]

training_patterns = [
    path('', views.training_center, name='training_center'),
    path('files/', include([
        path('', views.training_file_create, name='training_file_create'),
        path('upload/', views.training_file_upload, name='training_file_upload'),
        path('<int:file_id>/', include([
            path('', views.training_file_create, name='training_file_edit'),
            path('download-training-file/', views.training_file_download, name='training_file_download'),
            path('delete/', views.training_file_delete, name='training_file_delete'),
        ])),
    ])),
    path('train/', views.training_ai, name='training_ai'),
    path('capture/toggle/', views.capture_toggle, name='capture_toggle'),
    path('tokens/<uuid:token_id>/ai/<int:ai_id>/get-examples', 
         views.capture_get_examples, 
         name='capture_get_examples'),
]

urlpatterns = [
    path('tokens/<uuid:token_id>/', include([
        path('ai/', include(ai_patterns)),
        path('prompt-config/', views.prompt_config, name='prompt-config'),
    ])),
    path('training/', include(training_patterns)),
]