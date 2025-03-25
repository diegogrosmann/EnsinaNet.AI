# accounts/tests/test_context_processors.py

from django.test import TestCase, RequestFactory
from django.contrib.sites.models import Site
from accounts.context_processors import site_info

class SiteInfoContextProcessorTest(TestCase):
    """Testes para o context processor 'site_info'."""

    def setUp(self):
        """Configura o ambiente de testes."""
        self.factory = RequestFactory()
        self.site, _ = Site.objects.update_or_create(
            domain="example.com",
            defaults={'name': "Exemplo"}
        )

    def test_retorno_com_site_configurado(self):
        """
        Testa se retorna 'SITE_NAME' e 'SITE_DOMAIN' corretamente
        quando o site está configurado.
        """
        request = self.factory.get("/")
        context = site_info(request)
        self.assertEqual(context["SITE_NAME"], self.site.name)
        self.assertEqual(context["SITE_DOMAIN"], self.site.domain)
