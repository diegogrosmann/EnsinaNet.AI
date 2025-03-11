"""Admin interface para visualização de logs da API.

Configura a interface administrativa para visualizar e gerenciar 
logs de requisições à API.
"""

import logging
from typing import Optional, Any

from django.contrib import admin
from django.http import HttpRequest
from django.db.models import QuerySet

from .models import APILog

logger = logging.getLogger(__name__)

@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    """Interface administrativa para logs de API.
    
    Permite visualizar e filtrar logs das requisições feitas à API.
    
    Attributes:
        list_display: Colunas exibidas na listagem.
        list_filter: Filtros disponíveis.
        search_fields: Campos pesquisáveis.
        readonly_fields: Campos que não podem ser editados.
        ordering: Ordenação padrão dos registros.
    """
    
    list_display = ('id', 'user', 'user_token', 'path', 'method', 
                   'status_code', 'execution_time', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp', 'user')
    search_fields = ('path', 'user_token__key', 'user__email')
    readonly_fields = ('id', 'user', 'user_token', 'path', 'method', 
                      'status_code', 'execution_time', 'timestamp')
    ordering = ('-timestamp',)
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Otimiza o queryset carregando relacionamentos.
        
        Args:
            request: Requisição HTTP.
            
        Returns:
            QuerySet otimizado com related fields.
        """
        return super().get_queryset(request).select_related(
            'user', 'user_token'
        )
    
    def has_add_permission(self, request: HttpRequest) -> bool:
        """Desabilita adição manual de logs.
        
        Args:
            request: Requisição HTTP.
            
        Returns:
            bool: False, pois logs são gerados automaticamente.
        """
        return False
        
    def has_change_permission(self, request: HttpRequest, obj: Optional[Any] = None) -> bool:
        """Desabilita edição de logs.
        
        Args:
            request: Requisição HTTP.
            obj: Objeto sendo editado.
            
        Returns:
            bool: False, pois logs não devem ser alterados.
        """
        return False