# myapp/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from datetime import datetime
from .models import Profile

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Cria o perfil para um novo usuário.
    
    Argumentos:
        sender (Model): A classe do model.
        instance (User): Instância do usuário.
        created (bool): Indica se o usuário foi criado.
        **kwargs: Argumentos adicionais.
    
    Retorna:
        None
    """
    if created:
        Profile.objects.create(user=instance)
        logger.info(f"Perfil criado para o usuário: {instance.email}")

@receiver(post_save, sender=Profile)
def handle_user_approval(sender, instance, created, **kwargs):
    """Gerencia a aprovação do perfil do usuário.
    
    Argumentos:
        sender (Model): A classe do model.
        instance (Profile): Instância do perfil.
        created (bool): Indica se o perfil foi criado.
        **kwargs: Argumentos adicionais.
    
    Retorna:
        None
    """
    if not created:
        if instance.is_approved:
            user = instance.user
            user.is_active = True  # Ativa a conta após aprovação
            user.save()
            
            try:
                # Obtém o objeto Site atual
                current_site = Site.objects.get_current()
                
                # Prepara o contexto para o email
                context = {
                    'user': user,
                    'login_url': f"https://{current_site.domain}{reverse('accounts:login')}",
                    'current_site': current_site
                }
                
                # Renderiza o email HTML
                email_html = render_to_string('account/email/account_approved_email.html', context)
                
                subject = 'Sua conta foi aprovada!'
                message = 'Olá, sua conta foi aprovada pelo administrador e agora você pode fazer login.'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [user.email]
                
                send_mail(subject, message, from_email, recipient_list, html_message=email_html)
                logger.info(f"Notificação enviada ao usuário aprovado: {user.email}")
            except Exception as e:
                logger.error(f"Erro ao enviar e-mail de aprovação para o usuário {user.email}: {e}")
        else:
            # Quando um perfil não está aprovado, notifica o admin
            try:
                admin_email = settings.ADMIN_EMAIL
                user = instance.user
                
                # Obtém o objeto Site atual
                current_site = Site.objects.get_current()
                
                # Prepara o contexto para o email
                context = {
                    'user': user,
                    'registration_date': datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'admin_url': '/admin/accounts/profile/',
                    'current_site': current_site
                }
                
                # Renderiza o email HTML
                email_html = render_to_string('account/email/new_user_approval_email.html', context)
                
                subject = 'Novo Usuário Registrado para Aprovação'
                message = f'O usuário "{instance.user.email}" se registrou e está aguardando aprovação.'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [admin_email]
                
                send_mail(subject, message, from_email, recipient_list, html_message=email_html)
                logger.info(f"Notificação enviada ao admin sobre o novo usuário: {instance.user.email}")
            except Exception as e:
                logger.error(f"Erro ao enviar e-mail para o admin: {e}")
