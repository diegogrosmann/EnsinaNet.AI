# ai_config/tests/test_storage.py

import os
import tempfile
from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock
from ai_config.storage import OverwriteStorage

@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class OverwriteStorageTest(TestCase):
    """Testes para a classe OverwriteStorage, que sobrescreve arquivos existentes."""

    def setUp(self):
        """Cria instância do storage e gera arquivos temporários."""
        self.storage = OverwriteStorage()
        self.existing_filename = "existing_file.txt"
        self.existing_filepath = os.path.join(self.storage.location, self.existing_filename)
        
        # Cria um arquivo existente para simular
        with open(self.existing_filepath, 'w', encoding='utf-8') as f:
            f.write("Conteúdo antigo")

    def test_get_available_name_sobrescreve_arquivo_existente(self):
        """
        Testa se o get_available_name apaga o arquivo existente e retorna o mesmo nome.
        """
        with patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            
            returned_name = self.storage.get_available_name(self.existing_filename)
            
            mock_remove.assert_called_once()
            self.assertEqual(returned_name, self.existing_filename)

    def test_get_available_name_arquivo_inexistente(self):
        """
        Testa get_available_name quando o arquivo não existe.
        """
        new_filename = "new_file.txt"
        with patch('os.path.exists', return_value=False), \
             patch('os.remove') as mock_remove:
            
            returned_name = self.storage.get_available_name(new_filename)
            
            mock_remove.assert_not_called()
            self.assertEqual(returned_name, new_filename)
    
    def test_excecao_ao_remover_arquivo(self):
        """
        Testa se uma exceção ao remover arquivo é logada e relançada corretamente.
        Simula erro de permissão, por exemplo.
        """
        # Configurar o mock do logger de forma diferente
        with patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=PermissionError("Sem permissão")), \
             patch('ai_config.storage.logger') as mock_logger:
            
            # Garantir que uma exceção é levantada
            with self.assertRaises(PermissionError):
                self.storage.get_available_name(self.existing_filename)
            
            # Verificar qualquer chamada ao método error do logger
            mock_logger.error.assert_called()
