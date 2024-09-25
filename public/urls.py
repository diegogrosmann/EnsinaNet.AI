from django.urls import path
from . import views

app_name = 'public'

urlpatterns = [
    path('', views.index, name='index'),  # Mapeia a raiz para a view index
    # Adicione outras rotas públicas aqui
]
