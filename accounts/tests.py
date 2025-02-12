from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.exceptions import AuthenticationFailed
from unittest.mock import patch

from accounts.authentication import CustomTokenAuthentication
from accounts.backends import EmailBackend
from accounts.models import Profile, UserToken
from accounts.forms import CustomUserCreationForm, TokenForm, EmailAuthenticationForm

import uuid


User = get_user_model()

#
# Testes de autenticação (CustomTokenAuthTest)
#
class CustomTokenAuthTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='authuser', email='auth@example.com', password='pass')
        self.token = UserToken.objects.create(user=self.user, name='mytoken')

    def test_authenticate_credentials_valid(self):
        auth = CustomTokenAuthentication()
        user, token = auth.authenticate_credentials(self.token.key)
        self.assertEqual(user, self.user)
        self.assertEqual(token.key, self.token.key)

    def test_authenticate_credentials_invalid(self):
        auth = CustomTokenAuthentication()
        with self.assertRaises(AuthenticationFailed):
            auth.authenticate_credentials('invalidtoken')


#
# Testes de views (RegisterViewTest, LoginViewTest, LogoutViewTest)
#
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
                'password1': 'test1234',
                'password2': 'test1234'
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


#
# Testes de EmailBackend
#
class EmailBackendTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.backend = EmailBackend()
        self.user = User.objects.create_user(username='test@example.com', email='test@example.com', password='pass123')

    def test_authenticate_valid(self):
        request = self.factory.post('/login/')
        user = self.backend.authenticate(request, username='test@example.com', password='pass123')
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'test@example.com')

    def test_authenticate_invalid(self):
        request = self.factory.post('/login/')
        user = self.backend.authenticate(request, username='wrong@example.com', password='pass123')
        self.assertIsNone(user)


#
# Testes de signals
#
class SignalsTest(TestCase):
    def test_create_user_profile_signal(self):
        user = User.objects.create_user(username='signaluser', email='signal@example.com', password='pass')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_handle_user_approval_sends_email(self):
        user = User.objects.create_user(username='approver', email='approver@example.com', password='pass')
        profile = user.profile
        profile.is_approved = True
        profile.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Sua conta foi aprovada!', mail.outbox[0].subject)


#
# Testes de models (Profile, UserToken)
#
class ProfileModelTest(TestCase):
    def test_profile_str(self):
        user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass')
        profile = user.profile
        profile.is_approved = True
        self.assertEqual(str(profile), f"{user.email} Profile")

    def test_profile_defaults(self):
        user = User.objects.create_user(username='test2', email='test2@example.com', password='testpass')
        profile = Profile.objects.get(user=user)
        self.assertFalse(profile.is_approved)


class UserTokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='myuser', email='myuser@example.com', password='testpass')

    def test_user_token_creation(self):
        token = UserToken.objects.create(user=self.user, name='MeuToken')
        self.assertIsNotNone(token.id)
        self.assertEqual(token.user, self.user)
        self.assertTrue(len(token.key) > 0)

    def test_user_token_str(self):
        token = UserToken.objects.create(user=self.user, name='MyToken')
        self.assertIn('MyToken', str(token))
        self.assertIn(token.key, str(token))

    def test_generate_unique_key(self):
        token = UserToken.objects.create(user=self.user, name='Xpto')
        key_original = token.key
        token.save()
        self.assertEqual(key_original, token.key)


#
# Testes de forms (CustomUserCreationForm, EmailAuthenticationForm, TokenForm)
#
class CustomUserCreationFormTest(TestCase):
    def test_valid_data(self):
        form_data = {
            'email': 'newuser@example.com',
            'password1': 's3cret123',
            'password2': 's3cret123'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertFalse(user.is_active)
        user.save()

    def test_password_mismatch(self):
        form_data = {
            'email': 'newuser@example.com',
            'password1': 'secret123',
            'password2': 'different'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())


class EmailAuthenticationFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='loginuser', email='login@example.com', password='pass')

    def test_auth_success(self):
        form_data = {
            'email': 'login@example.com',
            'password': 'pass'
        }
        form = EmailAuthenticationForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_user(), self.user)

    def test_auth_fail(self):
        form_data = {
            'email': 'login@example.com',
            'password': 'wrong'
        }
        form = EmailAuthenticationForm(data=form_data)
        self.assertFalse(form.is_valid())


class TokenFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', email='test@example.com', password='pass')

    def test_unique_token_name_per_user(self):
        from accounts.models import UserToken
        UserToken.objects.create(user=self.user, name='MeuToken')
        form_data = {'name': 'MeuToken'}
        form = TokenForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('Já existe um token com esse nome.', str(form.errors))
