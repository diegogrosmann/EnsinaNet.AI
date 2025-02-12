from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from accounts.models import Profile, UserToken

User = get_user_model()

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
