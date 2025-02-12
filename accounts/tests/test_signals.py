from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from accounts.models import Profile

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
