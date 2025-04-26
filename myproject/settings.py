"""Configurações do Django para o projeto myproject.

Carrega variáveis de ambiente e define todas as configurações necessárias.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from celery.schedules import crontab

logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()
logger.info("Variáveis de ambiente carregadas")

# Configurações básicas
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key')
DEBUG = True
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    # Aplicações padrão do Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Aplicações de terceiros
    'rest_framework',
    'rest_framework.authtoken',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'markdownx',

    # Aplicações locais
    'accounts',
    'api',
    'public',
    'ai_config',
    'client_version',
    'core'
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = (
    'accounts.backends.EmailBackend',  # Seu backend personalizado
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
<<<<<<< HEAD
=======
ACCOUNT_EMAIL_CONFIRMATION_HTML_TEMPLATE = "accounts/registration/email_confirmation_message.html"
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)

# REST_FRAMEWORK = {
#     'DEFAULT_AUTHENTICATION_CLASSES': (
#         'accounts.authentication.CustomTokenAuthentication',
#     ),
#     'DEFAULT_PERMISSION_CLASSES': (
#         'rest_framework.permissions.IsAuthenticated',
#     ),
#     'EXCEPTION_HANDLER': 'api.exception_handlers.custom_exception_handler',
#     'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
#     'DEFAULT_VERSION': 'v1',
#     'ALLOWED_VERSIONS': ['v1'],  # Defina aqui todas as versões que sua API suportará
# }

<<<<<<< HEAD
# Ajustar redirecionamentos
# LOGIN_REDIRECT_URL = 'accounts:tokens'
# LOGOUT_REDIRECT_URL = 'accounts:login'
# LOGIN_URL = 'accounts:login'
# LOGOUT_URL = 'accounts:logout'

# URLs de redirecionamento após confirmação de email
# ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = 'accounts:login'
# ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = 'accounts:login'
=======
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.CustomTokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER': 'api.exception_handlers.custom_exception_handler',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],  # Defina aqui todas as versões que sua API suportará
}

# Ajustar redirecionamentos
LOGIN_REDIRECT_URL = 'accounts:tokens'
LOGOUT_REDIRECT_URL = 'accounts:login'
LOGIN_URL = 'accounts:login'
LOGOUT_URL = 'accounts:logout'

# URLs de redirecionamento após confirmação de email
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = 'accounts:login'
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = 'accounts:login'
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)

# Use a confirmação de email via GET
ACCOUNT_CONFIRM_EMAIL_ON_GET = True

# Desative o uso de HMAC se estiver enfrentando problemas
ACCOUNT_EMAIL_CONFIRMATION_HMAC = False

#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Para desenvolvimento
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Para produção

# Configurações para SMTP (Exemplo)
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')  # Adicione esta linha para definir o email do administrador

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.global_exception_middleware.GlobalExceptionMiddleware',
    'api.middleware.monitoring_middleware.MonitoringMiddleware', 
    
]

ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',  
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.site_info', 
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Adicionado

# Adicione os diretórios de arquivos estáticos adicionais se necessário
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
    # Outras pastas de estáticos
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOG_DIR = os.path.join(BASE_DIR, 'logs')

# Criar diretório de Log
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
    logger.info(f"Diretório de logs criado: {LOG_DIR}")

# Ajusta o nível do Log
if DEBUG:
    LOG_LEVEL = 'DEBUG'
else:
    LOG_LEVEL = 'ERROR'

# Configuração do logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'standard' if DEBUG else 'simple',
        },
        'root_file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'root.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
        'accounts_file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'accounts.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
        'api_file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'api.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
        'public_file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'public.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
        'django_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
        'django_request_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'django_request.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
        'ai_config_file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'ai_config.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
<<<<<<< HEAD
        'tasks_file': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'standard',
            'filename': os.path.join(LOG_DIR, 'tasks.log'),
            'maxBytes': 1024*1024*5,  # 5 MB
            'backupCount': 5,
        },
=======
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
    },
    'loggers': {
        '': {  # Root logger
            'handlers': ['console', 'root_file'],
            'level': LOG_LEVEL,
            'propagate': True,
        },
        'django': {
            'handlers': ['django_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['django_request_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['accounts_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'api': {
            'handlers': ['api_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'public': {
            'handlers': ['public_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'ai_config': {
            'handlers': ['ai_config_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
<<<<<<< HEAD
        'ai_config.tasks': {
            'handlers': ['tasks_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
=======
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
    }
}

# Arquivos de mídia
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

# Arquivos estáticos
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

<<<<<<< HEAD
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Log final da inicialização
logger.info("Configurações do projeto carregadas com sucesso")
=======
>>>>>>> 8a343d3 (Adiciona namespace às URLs da API e corrige redirecionamento na view de índice; remove arquivos JSON temporários e atualiza templates para usar URLs nomeadas com namespace.)
