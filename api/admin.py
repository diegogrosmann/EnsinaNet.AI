"""
Módulo de administração da aplicação API.
"""

import os
import logging

from django import forms
from django.conf import settings
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import admin, messages
from django.utils.html import format_html

# Caso use forms do DRF ou algo assim, mantenha-os.
# Import original do code snippet do README:
from api.utils.clientsIA import AI_CLIENT_MAPPING

# Se tiver AIClientGlobalConfiguration ou outros, preserve.
# Import do APILog (NOVO)
from .models import APILog

logger = logging.getLogger(__name__)

# Se você tiver outro admin de configurações (AIClientConfigurationAdmin etc.), mantenha-os.
# Exemplo, do snippet original:
# from .models import AIClientGlobalConfiguration, AIClientConfiguration, ...

# (NOVO) Registramos o APILog:
@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    """
    Admin para o modelo APILog, permitindo ver logs de requisições da API.
    """
    list_display = ('id', 'user', 'user_token', 'path', 'method', 'status_code', 'execution_time', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp')
    search_fields = ('path', 'user_token__key')
    readonly_fields = ('id', 'user_token', 'path', 'method', 'status_code', 'execution_time', 'timestamp')