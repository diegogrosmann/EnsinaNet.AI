# myapp/context_processors.py

from django.contrib.sites.models import Site

def site_info(request):
    """Retorna informações do site atual.
    
    Argumentos:
        request (HttpRequest): Objeto da requisição HTTP.
    
    Retorna:
        dict: Dicionário contendo 'SITE_NAME' e 'SITE_DOMAIN'.
    """
    current_site = Site.objects.get_current()
    return {
        'SITE_NAME': current_site.name,
        'SITE_DOMAIN': current_site.domain,
    }
