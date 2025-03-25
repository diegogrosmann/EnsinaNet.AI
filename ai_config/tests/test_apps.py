# ai_config/tests/test_apps.py

from django.test import TestCase
from django.apps import apps
from ai_config.apps import AiConfigConfig

class AiConfigConfigTest(TestCase):
    """Testes para a configuração do aplicativo ai_config."""

    def test_app_config_instalado(self):
        """
        Testa se o app 'ai_config' está configurado e registrado corretamente no Django.
        """
        self.assertIn('ai_config', apps.app_configs)
        self.assertIsInstance(apps.get_app_config('ai_config'), AiConfigConfig)

    def test_app_ready_log(self):
        """
        Testa se o método 'ready()' do app pode ser chamado sem erro.
        Embora não verifique diretamente logs, garante que não haja exceções.
        """
        app_config = apps.get_app_config('ai_config')
        # Chama o ready manualmente para ver se não explode
        app_config.ready()
        # Se não levantar exceções, consideramos ok
        self.assertTrue(True)
