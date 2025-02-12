from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from accounts.forms import CustomUserCreationForm, EmailAuthenticationForm, TokenForm

User = get_user_model()

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
