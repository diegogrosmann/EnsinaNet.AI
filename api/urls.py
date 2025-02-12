"""
URLs do aplicativo api.

Inclui:
    - Redirecionamento para /api/v1/compare/
    - Rotas de versão 1
    - Rotas de monitoramento
"""

from django.urls import path, include
from django.views.generic import RedirectView

# Import das views de monitoring
from api.views.monitoring import monitoring_dashboard, monitoring_data

urlpatterns = [
    # Redireciona /api/compare -> /api/v1/compare/
    path('compare/', RedirectView.as_view(url='/api/v1/compare/', permanent=True)),

    path('v1/', include(('api.v1.urls', 'api.v1'))),

    # Rotas para o painel de monitoramento
    # Agora qualquer user logado pode acessar, e a view filtra logs
    path('monitoring/', monitoring_dashboard, name='monitoring_dashboard'),
    path('monitoring/data/', monitoring_data, name='monitoring_data'),
]
