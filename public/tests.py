"""Testes para o aplicativo public.

Este módulo contém testes para as views e funcionalidades públicas.
"""

from django.test import TestCase, Client
from django.urls import reverse

class PublicViewsTests(TestCase):
    """Testes para as views públicas."""
    
    def setUp(self):
        """Configura ambiente para os testes."""
        self.client = Client()
    
    def test_index_view(self):
        """Testa a view da página inicial."""
        response = self.client.get(reverse('public:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'public/index.html')
    
    def test_index_redirect_authenticated(self):
        """Testa redirecionamento de usuários autenticados."""
        # TODO: Implementar teste com usuário autenticado
        pass
