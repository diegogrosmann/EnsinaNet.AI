"""
Signals para a aplicação accounts.

Este módulo contém os signals responsáveis por criar perfis de usuário automaticamente,
gerenciar aprovação de usuários e enviar emails de notificação relacionados.
A documentação segue o padrão Google e os logs são padronizados.
"""

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
    """Cria o perfil para um novo usuário automaticamente.

    Args:
        sender: A classe do model que enviou o signal.
        instance: Instância do usuário que foi salva.
        created (bool): Indica se é uma criação (True) ou atualização (False).
        **kwargs: Argumentos adicionais.
    """
    if created:
        try:
            Profile.objects.create(user=instance)
            logger.info(f"Perfil criado automaticamente para o usuário: {instance.email}")
        except Exception as e:
            logger.error(f"Erro ao criar perfil para o usuário {instance.email}: {str(e)}", exc_info=True)


@receiver(post_save, sender=Profile)
def handle_user_approval(sender, instance, created, **kwargs):
    """Gerencia a aprovação do perfil e envia notificações apropriadas.

    Args:
        sender: A classe do model que enviou o signal.
        instance: Instância do perfil que foi salvo.
        created (bool): Indica se é uma criação (True) ou atualização (False).
        **kwargs: Argumentos adicionais.
    """
    if not created:
        if instance.is_approved:
            user = instance.user
            try:
                user.is_active = True  # Ativa a conta após aprovação
                user.save(update_fields=['is_active'])
                logger.info(f"Usuário ativado após aprovação: {user.email}")
                try:
                    current_site = Site.objects.get_current()
                except Exception:
                    logger.error("Site não configurado no banco de dados", exc_info=True)
                    current_site = type('obj', (object,), {'domain': 'example.com', 'name': 'Site'})
                context = {
                    'user': user,
                    'login_url': f"https://{current_site.domain}{reverse('accounts:login')}",
                    'current_site': current_site
                }
                try:
                    email_html = render_to_string('account/email/account_approved_email.html', context)
                    subject = 'Sua conta foi aprovada!'
                    message = 'Olá, sua conta foi aprovada pelo administrador e agora você pode fazer login.'
                    from_email = settings.DEFAULT_FROM_EMAIL
                    recipient_list = [user.email]
                    send_mail(subject, message, from_email, recipient_list, html_message=email_html)
                    logger.info(f"Notificação de aprovação enviada ao usuário: {user.email}")
                except Exception as e:
                    logger.error(f"Erro ao enviar e-mail de aprovação para {user.email}: {str(e)}", exc_info=True)
            except Exception as e:
                logger.error(f"Erro ao processar aprovação do usuário {user.email}: {str(e)}", exc_info=True)
        else:
            try:
                admin_email = getattr(settings, 'ADMIN_EMAIL', None)
                if not admin_email:
                    logger.error("ADMIN_EMAIL não configurado em settings")
                    return
                user = instance.user
                try:
                    current_site = Site.objects.get_current()
                except Exception:
                    logger.error("Site não configurado no banco de dados", exc_info=True)
                    current_site = type('obj', (object,), {'domain': 'example.com', 'name': 'Site'})
                context = {
                    'user': user,
                    'registration_date': datetime.now().strftime("%d/%m/%Y %H:%M"),
                    'admin_url': '/admin/accounts/profile/',
                    'current_site': current_site
                }
                try:
                    email_html = render_to_string('account/email/new_user_approval_email.html', context)
                    subject = 'Novo Usuário Registrado para Aprovação'
                    message = f'O usuário "{user.email}" se registrou e está aguardando aprovação.'
                    from_email = settings.DEFAULT_FROM_EMAIL
                    recipient_list = [admin_email]
                    send_mail(subject, message, from_email, recipient_list, html_message=email_html)
                    logger.info(f"Notificação enviada ao admin sobre o novo usuário: {user.email}")
                except Exception as e:
                    logger.error(f"Erro ao enviar e-mail para o admin sobre {user.email}: {str(e)}", exc_info=True)
            except Exception as e:
                logger.error(f"Erro ao processar notificação de novo usuário: {str(e)}", exc_info=True)
