# ai_config/tests/test_training_files.py

import os
import json
import tempfile
from io import BytesIO

from django.urls import reverse
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from ai_config.models import AITrainingFile
from core1.types import APPResponse

User = get_user_model()

@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class TrainingFileUploadViewTest(TestCase):
    """Testes para a view training_file_upload."""

    def setUp(self):
        """Cria um usuário de teste e faz login."""
        self.user = User.objects.create_user(username="teste", email="teste@example.com", password="12345")
        self.client.login(username="teste", password="12345")
        self.url = reverse("ai_config:training_center")  # redireciona para o centro, conforme a view

    def test_upload_metodo_nao_post(self):
        """Verifica se método diferente de POST retorna erro."""
        response = self.client.get(reverse("ai_config:training_file_upload"))
        self.assertRedirects(response, self.url)
        # Pode verificar a mensagem de erro no conteúdo

    def test_upload_sem_arquivo(self):
        """Verifica se a ausência de arquivo gera mensagem de erro."""
        response = self.client.post(reverse("ai_config:training_file_upload"), data={"name": "arquivo.json"})
        # Se for AJAX, o retorno é JSON; caso contrário, redireciona
        if response["Content-Type"].startswith("application/json"):
            data = json.loads(response.content)
            self.assertFalse(data["success"])
            self.assertIn("Nenhum arquivo enviado", data["error"])
        else:
            self.assertRedirects(response, self.url)

    def test_upload_valido(self):
        """Testa upload válido de arquivo de treinamento."""
        # Cria um arquivo simples (em memória)
        file_content = b'{"examples": []}'
        uploaded_file = SimpleUploadedFile("teste.json", file_content, content_type="application/json")
        post_data = {"name": "teste.json"}
        response = self.client.post(
            reverse("ai_config:training_file_upload"),
            data={"name": "teste.json"},
            files={"file": uploaded_file}
        )
        # Se for AJAX
        if response["Content-Type"].startswith("application/json"):
            data = json.loads(response.content)
            self.assertTrue(data["success"])
            self.assertIn("criado com sucesso", data["data"]["message"])
        else:
            self.assertRedirects(response, self.url)
        # Verifica se o arquivo foi criado no BD
        self.assertTrue(AITrainingFile.objects.filter(user=self.user, name="teste.json").exists())


class TrainingFileFormViewTest(TestCase):
    """Testes para a view training_file_form (criação/edição de arquivo)."""

    def setUp(self):
        """Cria usuário, faz login e cria um arquivo de treinamento para edição."""
        self.user = User.objects.create_user(username="formuser", email="formuser@example.com", password="12345")
        self.client.login(username="formuser", password="12345")
        self.training_file = AITrainingFile.objects.create(
            user=self.user,
            name="arquivo_existente",
            file_data=b'{"examples": []}'
        )
        self.url_edit = reverse("ai_config:training_file_edit", args=[self.training_file.id])
        self.url_form = reverse("ai_config:training_file_form")  # para criação

    def test_form_get_edit(self):
        """Verifica se a view de edição (GET) retorna status 200 e utiliza o template correto."""
        response = self.client.get(self.url_edit)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "training/file_form.html")

    def test_form_post_edicao_valida(self):
        """Testa o POST com dados válidos para edição do arquivo."""
        # Simula envio de um novo nome e um conjunto de exemplos
        post_data = {
            "name-name": "arquivo_editado",  # prefix 'name' do formulário de nome
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-user_message": "Pergunta?",
            "form-0-response": "Resposta!",
            "form-0-system_message": "",
        }
        response = self.client.post(self.url_edit, data=post_data)
        # Após sucesso, redireciona para training_center
        self.assertRedirects(response, reverse("ai_config:training_center"))
        self.training_file.refresh_from_db()
        self.assertEqual(self.training_file.name, "arquivo_editado")

class TrainingFileDownloadViewTest(TestCase):
    """Testes para a view training_file_download."""

    def setUp(self):
        """Cria usuário, faz login e cria um arquivo de treinamento com conteúdo real."""
        self.user = User.objects.create_user(username="downloaduser", email="download@example.com", password="12345")
        self.client.login(username="downloaduser", password="12345")
        self.training_file = AITrainingFile.objects.create(
            user=self.user,
            name="arquivo_download",
            file_data=b'{"examples": []}'
        )
        self.url = reverse("ai_config:training_file_download", args=[self.training_file.id])

    def test_download_arquivo_existente(self):
        """Verifica se o download de um arquivo existente retorna um FileResponse."""
        response = self.client.get(self.url)
        # Deve ter Content-Disposition de attachment
        self.assertIn("attachment", response.get("Content-Disposition", ""))
    
    def test_download_arquivo_inexistente(self):
        """Verifica se tentar baixar um arquivo inexistente redireciona com mensagem de erro."""
        url = reverse("ai_config:training_file_download", args=[9999])
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("ai_config:training_center"))
        self.assertContains(response, "Arquivo não encontrado")

class TrainingFileDeleteViewTest(TestCase):
    """Testes para a view training_file_delete."""

    def setUp(self):
        """Cria usuário, faz login e cria um arquivo para exclusão."""
        self.user = User.objects.create_user(username="deleteuser", email="delete@example.com", password="12345")
        self.client.login(username="deleteuser", password="12345")
        self.training_file = AITrainingFile.objects.create(
            user=self.user,
            name="arquivo_delete",
            file_data=b'{"examples": []}'
        )
        self.url = reverse("ai_config:training_file_delete", args=[self.training_file.id])

    def test_delete_metodo_nao_permitido(self):
        """Verifica se método GET não é permitido para exclusão."""
        response = self.client.get(self.url)
        # Se for AJAX, retorna JSON com erro; se não, redireciona
        if response["Content-Type"].startswith("application/json"):
            data = json.loads(response.content)
            self.assertFalse(data["success"])
        else:
            self.assertRedirects(response, reverse("ai_config:training_center"))

    def test_delete_valido(self):
        """Testa a exclusão via método POST."""
        response = self.client.post(self.url)
        # Se for AJAX
        if response["Content-Type"].startswith("application/json"):
            data = json.loads(response.content)
            self.assertTrue(data["success"])
        else:
            self.assertRedirects(response, reverse("ai_config:training_center"))
        self.assertFalse(AITrainingFile.objects.filter(id=self.training_file.id).exists())


# Fim de test_training_files.py
