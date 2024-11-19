from django.urls import path
from . import views

app_name = 'ai_config'

urlpatterns = [
    path('manage-ai-configurations/<uuid:token_id>/', views.manage_ai_configurations, name='manage_ai_configurations'),
    path('manage-token-configurations/<uuid:token_id>/', views.manage_token_configurations, name='manage_token_configurations'),
    path('upload-training-file/<uuid:token_id>/', views.upload_training_file, name='upload_training_file'),
    path('manage-training-configurations/<uuid:token_id>/', views.manage_training_configurations, name='manage_training_configurations'),
    path('train-ai/<uuid:token_id>/', views.train_ai, name='train_ai'),
    path('training-file/', views.create_or_edit_training_file, name='create_training_file'),
    path('training-file/<int:file_id>/', views.create_or_edit_training_file, name='edit_training_file'),
    path('download-training-file/<int:file_id>/', views.download_training_file, name='download_training_file'),
    path('delete-training-file/<int:file_id>/', views.delete_training_file, name='delete_training_file'),
]


