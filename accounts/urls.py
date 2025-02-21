"""URLs do aplicativo accounts."""
from django.urls import path, include
from . import views

app_name = 'accounts'

auth_patterns = [
    path('register/', views.auth_register, name='register'),
    path('login/', views.auth_login, name='login'),
    path('logout/', views.auth_logout, name='logout'),
    path('confirm-email/<str:key>/', views.CustomConfirmEmailView.as_view(), name='account_confirm_email'),
    path('resend-confirmation/', views.auth_resend_confirmation, name='resend_confirmation'),
]

password_patterns = [
    path('reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('reset/done/', views.password_reset_done, name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('reset/complete/', views.password_reset_complete, name='password_reset_complete'),
]

token_patterns = [
    path('', views.tokens_manage, name='tokens_manage'),
    path('create/', views.token_create, name='token_create'),
    path('<uuid:token_id>/', include([
        path('edit/name/', views.token_edit_name, name='token_edit_name'),
        path('delete/', views.token_delete, name='token_delete'),
        path('config/', views.token_config, name='token_config'),
    ])),
]

urlpatterns = [
    path('auth/', include(auth_patterns)),
    path('password/', include(password_patterns)), 
    path('tokens/', include(token_patterns)),
    path('settings/', views.user_settings, name='user_settings'),
]
