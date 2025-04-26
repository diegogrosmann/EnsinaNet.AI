<<<<<<< HEAD
"""URLs da API.

Define os padrões de URL para endpoints de API e monitoramento,
estabelecendo as rotas de acesso para todos os recursos disponíveis.
"""

import logging
from anthropic import APIError
from django.urls import path, include
from django.urls.resolvers import URLPattern, URLResolver
from typing import List, Union

from api.views.monitoring import (
    monitoring_dashboard, 
    monitoring_data,
    monitoring_stats,
    monitoring_requests,
    monitoring_request_details
)
from api.views.healthcheck import healthcheck

logger = logging.getLogger(__name__)

app_name = 'api'

# URLs de monitoramento
monitoring_patterns: List[Union[URLPattern, URLResolver]] = [
    path('', monitoring_dashboard, name='monitoring_dashboard'),
    path('data/', monitoring_data, name='monitoring_data'),
    path('stats/', monitoring_stats, name='monitoring_stats'),
    path('requests/', monitoring_requests, name='monitoring_requests'),
    path('requests/<int:request_id>/', monitoring_request_details, name='monitoring_request_details'),
=======
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
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
]

# Todas as URLs da aplicação
urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path('healthcheck/', healthcheck, name='healthcheck'),
    path('monitoring/', include(monitoring_patterns)),
    path('v1/', include(('api.v1.urls', 'api.v1'), namespace='api_v1')),
]

# Log das URLs registradas
logger.info(f"URLs de monitoramento registradas: {len(monitoring_patterns)}")
logger.info("Todas as URLs da API inicializadas com sucesso")

def get_available_endpoints() -> List[str]:
    """Retorna uma lista de todos os endpoints disponíveis na API.
    
    Esta função é útil para documentação automática ou para
    debug de rotas disponíveis.
    
    Returns:
        List[str]: Lista de endpoints registrados.
    
    Raises:
        APIError: Se ocorrer erro ao analisar as URLs.
    """
    try:
        result = []
        
        # Processar URLs de monitoramento
        for pattern in monitoring_patterns:
            route = f"/api/monitoring{pattern.pattern}"
            result.append(route)
        
        # Nota: poderíamos expandir para outras URLs se necessário
        
        logger.debug(f"Endpoints disponíveis recuperados: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"Erro ao obter endpoints disponíveis: {str(e)}", exc_info=True)
        raise APIError(f"Erro ao processar rotas da API: {str(e)}")
