"""URLs da API.

Define os padrões de URL para endpoints de API e monitoramento.
"""

import logging
from django.urls import path, include
from django.urls.resolvers import URLPattern, URLResolver
from typing import List, Union

from api.views.monitoring import monitoring_dashboard, monitoring_data

logger = logging.getLogger(__name__)

app_name = 'api'

# URLs de monitoramento
monitoring_patterns: List[Union[URLPattern, URLResolver]] = [
    path('', monitoring_dashboard, name='monitoring_dashboard'),
    path('data/', monitoring_data, name='monitoring_data'),
]

# Todas as URLs da aplicação
urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path('monitoring/', include(monitoring_patterns)),
    path('v1/', include(('api.v1.urls', 'api.v1'), namespace='api_v1')),
]

# Log das URLs registradas
logger.debug("URLs de monitoramento registradas")
logger.debug("URLs da API v1 registradas")
logger.info("Todas as URLs da API inicializadas com sucesso")
