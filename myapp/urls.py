from django.urls import path
from . import views

urlpatterns = [
    path('', views.hello_world, name='index'),
    path('api/compare_lab/', views.compare_lab, name='compare_lab'),
    path('api/compare_instrucao/', views.compare_instrucao, name='compare_instrucao')
]