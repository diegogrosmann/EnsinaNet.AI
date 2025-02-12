from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from api.models import APILog
from accounts.models import UserToken

class MonitoringMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='mwuser', email='mw@example.com', password='pass')
        self.token = UserToken.objects.create(user=self.user, name='mwtoken')

    def test_monitoring_log_created(self):
        url = reverse('api.v1:compare')
        self.client.post(url, {}, HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertTrue(APILog.objects.exists())

    def test_monitoring_log_anonymous(self):
        url = reverse('api.v1:compare')
        self.client.post(url, {})
        self.assertTrue(APILog.objects.exists())
        self.assertIsNone(APILog.objects.first().user_token)
