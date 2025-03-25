import logging
from django.contrib.sites.models import Site

logger = logging.getLogger(__name__)

def site_info(request):
    """Retorna informações do site atual para o contexto de templates.

    Disponibiliza informações sobre o site atual para todos os templates renderizados.

    Args:
        request (HttpRequest): Objeto de requisição atual.

    Returns:
        dict: Dicionário contendo 'SITE_NAME' e 'SITE_DOMAIN'. Se ocorrer um erro,
              retorna valores padrão.
    """
    try:
        current_site = Site.objects.get_current()
        logger.debug(f"Informações de site carregadas: {current_site.name}")
        return {
            'SITE_NAME': current_site.name,
            'SITE_DOMAIN': current_site.domain,
        }
    except Site.DoesNotExist:
        logger.error("Site não configurado no banco de dados")
        return {
            'SITE_NAME': 'Site',
            'SITE_DOMAIN': 'example.com',
        }
    except Exception as e:
        logger.error(f"Erro ao carregar informações do site: {str(e)}", exc_info=True)
        return {
            'SITE_NAME': 'Site',
            'SITE_DOMAIN': 'example.com',
        }
