# ai_config/tests/test_urls.py

from django.test import TestCase
from django.urls import reverse, resolve
from ai_config import views

class AiConfigURLsTest(TestCase):
    """Testes para as URLs definidas em ai_config/urls.py."""

    def test_ai_manage_url(self):
        """Verifica se /ai/ resolve para a view manage_ai."""
        url = reverse('ai_config:ai_manage')
        self.assertEqual(resolve(url).func, views.manage_ai)

    def test_ai_create_url(self):
        """Verifica se /ai/create/ resolve para a view create_ai."""
        url = reverse('ai_config:ai_create')
        self.assertEqual(resolve(url).func, views.create_ai)

    def test_ai_edit_url(self):
        """Verifica se /ai/<id>/edit/ resolve para a view edit_ai."""
        url = reverse('ai_config:ai_edit', args=[123])
        self.assertEqual(resolve(url).func, views.edit_ai)

    def test_training_center_url(self):
        """Verifica se /training/ resolve para training_center."""
        url = reverse('ai_config:training_center')
        self.assertEqual(resolve(url).func, views.training_center)

    def test_training_file_create_url(self):
        """Verifica se /training/files/ resolve para training_file_form."""
        url = reverse('ai_config:training_file_create')
        self.assertEqual(resolve(url).func, views.training_file_form)

    def test_token_prompt_config_url(self):
        """Verifica se /token/<uuid>/prompt resolve para prompt_config."""
        url = reverse('ai_config:token_prompt_config', args=["bbf9b8b5-2bd1-42ee-9d5a-7dfa7a389752"])
        self.assertEqual(resolve(url).func, views.prompt_config)
    
    def test_non_existent_route(self):
        """Verifica se uma rota inexistente retorna 404."""
        response = self.client.get('/ai/doesnotexist/')
        self.assertEqual(response.status_code, 404)
