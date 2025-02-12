"""Testes para o módulo de extração de documentos.

Verifica a funcionalidade de extração de texto de diferentes tipos de arquivos
usando o docling e tratamento de erros.
"""

import unittest
from unittest.mock import patch
import base64

from api.utils.doc_extractor import extract_text
from api.exceptions import FileProcessingError

class TestDocExtractor(unittest.TestCase):
    """Testes do extrator de documentos.
    
    Verifica a extração de texto de PDFs e documentos Word,
    além de casos de erro.
    """
    
    def setUp(self):
        """Configura dados de teste.
        
        Prepara conteúdo base64 mock para os diferentes tipos de arquivo.
        """
        self.pdf_content = base64.b64encode(b'fake pdf content').decode()
        self.word_content = base64.b64encode(b'fake word content').decode()

    def test_extract_text_pdf(self):
        """Testa extração de texto de PDF.
        
        Verifica se o texto é extraído corretamente de um PDF válido
        usando o mock do conversor PDF.
        """
        with patch('api.utils.doc_extractor.convert_pdf_bytes_to_text') as mock_convert:
            mock_convert.return_value = "texto extraído"
            result = extract_text({'name': 'test.pdf', 'content': self.pdf_content})
            self.assertEqual(result, "texto extraído")

    def test_extract_text_word(self):
        """Testa extração de texto de documento Word.
        
        Verifica se o texto é extraído corretamente de um arquivo DOCX
        usando o mock do conversor Word.
        """
        with patch('api.utils.doc_extractor.convert_word_bytes_to_text') as mock_convert:
            mock_convert.return_value = "texto extraído"
            result = extract_text({'name': 'test.docx', 'content': self.word_content})
            self.assertEqual(result, "texto extraído")

    def test_extract_text_invalid_data(self):
        """Testa rejeição de dados inválidos.
        
        Verifica se a função levanta exceção apropriada quando recebe
        dados malformados.
        """
        with self.assertRaises(FileProcessingError):
            extract_text({})

    def test_extract_text_file_missing(self):
        """Testa rejeição de arquivo faltante.
        
        Verifica se a função levanta exceção quando campos obrigatórios
        estão ausentes.
        """
        with self.assertRaises(FileProcessingError):
            extract_text({'name': 'test.pdf'})

    def test_extract_text_unsupported_format(self):
        """Testa rejeição de formato não suportado.
        
        Verifica se a função levanta exceção para extensões de arquivo
        não suportadas.
        """
        with self.assertRaises(FileProcessingError):
            extract_text({'name': 'test.xyz', 'content': self.pdf_content})
