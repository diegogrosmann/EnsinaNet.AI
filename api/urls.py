from django.urls import path
from . import views

urlpatterns = [
    path('compare/', views.compare, name='compare'),
    # Adicione outras rotas da API aqui
]
