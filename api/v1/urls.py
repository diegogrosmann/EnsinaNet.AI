"""URLs para API v1.

Define os endpoints disponíveis na versão 1 da API, estabelecendo
as rotas de acesso para todos os recursos deste namespace.
"""

import logging
from django.urls import path

from api.exceptions import APIClientException
from .views import compare, compare_async, operation_status, operations_list

logger = logging.getLogger(__name__)

app_name = 'v1'

app_name = 'v1'

urlpatterns = [
<<<<<<< HEAD
    path('compare/', compare, name='compare'),
    path('compare/async/', compare_async, name='compare_async'),
    path('operations/<str:operation_id>/', operation_status, name='operation_status'),
    path('operations/', operations_list, name='operations_list'),
=======
    path('compare/', views.compare, name='compare'),
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
]

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
        raise APIClientException(f"Erro ao processar endpoints da API v1: {str(e)}")
