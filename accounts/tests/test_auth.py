from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

from accounts.authentication import CustomTokenAuthentication
from accounts.backends import EmailBackend
from accounts.models import UserToken

User = get_user_model()

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
