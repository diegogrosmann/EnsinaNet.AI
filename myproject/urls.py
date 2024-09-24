# myproject/urls.py

from django.contrib import admin
from django.urls import path, include
from myapp.views import CustomConfirmEmailView  # Importe a nova view personalizada

urlpatterns = [
    path('admin/', admin.site.urls),

    # Rotas de autenticação via API
    path('dj-rest-auth/', include('dj_rest_auth.urls')),
    path('dj-rest-auth/registration/', include('dj_rest_auth.registration.urls')),

    path('accounts/', include('allauth.urls')),

    # Rotas de frontend
    path('', include('myapp.urls')),

    # Use a nova rota para confirmação de email
    path(
        'account-confirm-email/<str:key>/',
        CustomConfirmEmailView.as_view(),
        name='account_confirm_email',
    ),
]
