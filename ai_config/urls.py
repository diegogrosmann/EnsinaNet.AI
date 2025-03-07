"""URLs do aplicativo ai_config."""
from django.urls import path, include
from ai_config import views

app_name = 'ai_config'

ai_patterns = [
    path('', views.manage_ai, name='ai_manage'),
    path('create/', views.create_ai, name='ai_create'),
    path('<int:ai_id>/', include([
        path('edit/', views.edit_ai, name='ai_edit'),
        path('delete/', views.delete_ai, name='ai_delete'),
        path('available-tokens/', views.ai_available_tokens, name='ai_available_tokens'),
        path('link-token/<uuid:token_id>/', views.ai_link_token, name='ai_link_token'),
    ])),
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
    path('capture/toggle/', views.capture_toggle, name='capture_toggle'),
    path('tokens/<uuid:token_id>/ai/<int:ai_id>/get-examples', 
         views.capture_get_examples, 
         name='capture_get_examples'),
    # Novos endpoints
    path('train/', views.training_ai, name='training_ai'),  # URL simplificada
    path('status/', views.training_status, name='training_status'),
    path('progress/', views.training_progress, name='training_progress'),
    path('cancel/<str:job_id>/', views.training_cancel, name='training_cancel'),
    path('delete/<str:job_id>/', views.training_delete, name='training_delete'),  # Nova URL
]

token_patterns = [
    path('prompt', views.prompt_config, name='token_prompt_config'),
    path('ai_link', views.token_ai_link, name='token_ai_link'),
]

urlpatterns = [ 
    path('ai/', include(ai_patterns)),
    path('training/', include(training_patterns)),
    path('token/<uuid:token_id>/', include(token_patterns)),
]