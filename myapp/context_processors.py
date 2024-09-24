# myapp/context_processors.py

from django.contrib.sites.models import Site

def site_info(request):
    current_site = Site.objects.get_current()
    return {
        'SITE_NAME': current_site.name,
        'SITE_DOMAIN': current_site.domain,
    }
