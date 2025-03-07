"""
Módulo de administração da aplicação API.
"""

import logging

from django.contrib import admin

from .models import APILog

logger = logging.getLogger(__name__)

@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    """
    Admin para o modelo APILog, permitindo ver logs de requisições da API.
    """
    list_display = ('id', 'user', 'user_token', 'path', 'method', 'status_code', 'execution_time', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp')
    search_fields = ('path', 'user_token__key')
    readonly_fields = ('id', 'user_token', 'path', 'method', 'status_code', 'execution_time', 'timestamp')