"""
Módulo para healthcheck da API.

Fornece um endpoint simples para verificar se a API está online e funcionando.
"""

import logging
from django.http import JsonResponse

from core.types import APPResponse

logger = logging.getLogger(__name__)

def healthcheck(request):
    """
    Endpoint para verificar a saúde da API.
    
    Retorna um JSON com status 'ok' se a API estiver funcionando.
    """
    logger.debug("Healthcheck endpoint acessado")
    response = APPResponse.create_success({'status': 'ok'})
    return JsonResponse(response.to_dict())
