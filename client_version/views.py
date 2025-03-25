import json
import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import ClientVersion

logger = logging.getLogger(__name__)

def get_latest_version(request, product_name):
    """
    Retorna a informação mais recente de versão para um produto específico em formato JSON.
    
    Endpoint acessado pelos clientes para verificar atualizações disponíveis.
    """
    try:
        # Busca a versão mais recente e ativa para o produto
        latest_version = ClientVersion.objects.filter(
            product_name=product_name,
            active=True
        ).order_by('-release_date').first()
        
        if not latest_version:
            logger.warning(f"Nenhuma versão ativa encontrada para o produto: {product_name}")
            return JsonResponse(
                {"error": "Version not found"}, 
                status=404
            )
        
        # Monta a resposta no formato esperado pelo cliente
        data = {
            "version": latest_version.version,
            "download_url": latest_version.download_url,
            "mandatory": latest_version.is_mandatory,
            "release_date": latest_version.release_date.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": latest_version.release_notes
        }
        
        logger.info(f"Versão {latest_version.version} do produto {product_name} solicitada")
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Erro ao buscar versão para {product_name}: {str(e)}")
        return JsonResponse(
            {"error": "Server error"},
            status=500
        )
