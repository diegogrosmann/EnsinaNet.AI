from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch

class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('register')

    def test_register_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/registration/register.html')

    def test_register_post_valid(self):
        with patch('accounts.views.send_email_confirmation') as mock_send_email:
            data = {
                'email': 'newuser@example.com',
                'password1': 'test1234@#$',
                'password2': 'test1234@#$'
            }
            response = self.client.post(self.url, data)
            
            # Verifica se houve redirecionamento
            self.assertEqual(response.status_code, 302)
            self.assertRedirects(response, reverse('login'))
            
            # Verifica se o usuário foi criado
            self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
            new_user = User.objects.get(email='newuser@example.com')
            self.assertFalse(new_user.is_active)
            
            # Verifica se o email de confirmação foi enviado
            mock_send_email.assert_called_once()

class LoginViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('login')
        self.user = User.objects.create_user(username='login', email='login@example.com', password='mypassword')

    def test_login_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/registration/login.html')

    def test_login_post_valid(self):
        data = {
            'email': 'login@example.com',
            'password': 'mypassword'
        }
        response = self.client.post(self.url, data, follow=True)
        self.assertRedirects(response, reverse('manage_tokens'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_post_invalid(self):
        data = {
            'email': 'login@example.com',
            'password': 'wrongpass'
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='123')
        self.client.login(username='test@example.com', password='123')

    def test_logout(self):
        url = reverse('logout')
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
