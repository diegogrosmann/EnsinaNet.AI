# myapp/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        logger.info(f"Perfil criado para o usuário: {instance.email}")

@receiver(post_save, sender=Profile)
def handle_user_approval(sender, instance, created, **kwargs):
    if not created:
        if instance.is_approved:
            user = instance.user
            user.is_active = True  # Ativa a conta após aprovação
            user.save()
            subject = 'Sua conta foi aprovada!'
            message = 'Olá, sua conta foi aprovada pelo administrador e agora você pode fazer login.'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            try:
                send_mail(subject, message, from_email, recipient_list)
                logger.info(f"Notificação enviada ao usuário aprovado: {user.email}")
            except Exception as e:
                logger.error(f"Erro ao enviar e-mail de aprovação para o usuário {user.email}: {e}")
        else:
            admin_email = settings.ADMIN_EMAIL
            subject = 'Novo Usuário Registrado para Aprovação'
            message = f'O usuário "{instance.user.email}" se registrou e está aguardando aprovação.'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [admin_email]
            try:
                send_mail(subject, message, from_email, recipient_list)
                logger.info(f"Notificação enviada ao admin sobre o novo usuário: {instance.user.email}")
            except Exception as e:
                logger.error(f"Erro ao enviar e-mail para o admin: {e}")
