"""URLs para API v1.

Define os endpoints disponíveis na versão 1 da API, estabelecendo
as rotas de acesso para todos os recursos deste namespace.
"""

import logging
from django.urls import path
from . import views
from core.exceptions import APIError

logger = logging.getLogger(__name__)

app_name = 'v1'

urlpatterns = [
    path('compare/', views.compare, name='compare'),
    path('async_compare/', views.async_compare, name='async_compare'),
    path('async_compare/<str:task_id>/', views.async_compare_status, name='async_compare_status'),
]

logger.info(f"Endpoints da API v1 registrados: {len(urlpatterns)}")

def get_api_endpoints() -> list:
    """Lista todos os endpoints disponíveis na API v1.
    
    Returns:
        list: Lista de strings contendo os caminhos dos endpoints disponíveis.
        
    Raises:
        APIError: Se ocorrer erro ao processar os endpoints.
    """
    try:
        endpoints = []
        for pattern in urlpatterns:
            endpoints.append(f"/api/v1{pattern.pattern}")
        logger.debug(f"Listados {len(endpoints)} endpoints na API v1")
        return endpoints
    except Exception as e:
        logger.error(f"Erro ao listar endpoints API v1: {str(e)}", exc_info=True)
        raise APIError(f"Erro ao processar endpoints da API v1: {str(e)}")
