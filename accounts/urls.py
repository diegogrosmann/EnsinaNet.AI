from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('manage-tokens/', views.manage_tokens, name='manage_tokens'),
    path('manage-tokens/delete/<uuid:token_id>/', views.delete_token, name='delete_token'),
    path('manage-tokens/<uuid:token_id>/configurations/', views.manage_configurations, name='manage_configurations'),

    # Rotas de redefinição de senha
    path('password_reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', views.password_reset_done_view, name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('reset/done/', views.password_reset_complete_view, name='password_reset_complete'),
]
