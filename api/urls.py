"""URLs do aplicativo api."""
from django.urls import path, include
from api.views.monitoring import monitoring_dashboard, monitoring_data

app_name = 'api'

urlpatterns = [
    # Monitoring
    path('monitoring/', include([
        path('', monitoring_dashboard, name='monitoring_dashboard'),
        path('data/', monitoring_data, name='monitoring_data'),
    ])),
    # API Versions
    path('v1/', include(('api.v1.urls', 'api.v1'), namespace='api_v1')),
]
