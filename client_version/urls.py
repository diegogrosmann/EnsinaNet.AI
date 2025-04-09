from django.urls import path
from . import views

app_name = 'client_version_api'

urlpatterns = [
    path('<str:product_name>/version.json', views.get_latest_version, name='get_latest_version'),
]
