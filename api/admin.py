"""Admin interface para visualização de logs da API.

Configura a interface administrativa para visualizar e gerenciar 
logs de requisições à API, facilitando a auditoria e análise
de problemas relacionados ao uso da API.
"""

import logging
import json
from typing import Optional, Any

from django.contrib import admin
from django.http import HttpRequest
from django.db.models import QuerySet
from django.utils.html import format_html
from django.contrib import messages

from .models import APILog
from core.models import AsyncTaskRecord

logger = logging.getLogger(__name__)

@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    """Interface administrativa para logs de API.
    
    Permite visualizar e filtrar logs das requisições feitas à API,
    com funcionalidades para melhor análise de tráfego e depuração.
    
    Attributes:
        list_display: Colunas exibidas na listagem.
        list_filter: Filtros disponíveis na lateral.
        search_fields: Campos pesquisáveis pelo admin.
        readonly_fields: Campos que não podem ser editados.
        ordering: Ordenação padrão dos registros.
        date_hierarchy: Campo usado para navegação por data.
        list_per_page: Número de registros por página.
    """
    
    list_display = ('id', 'user', 'user_token', 'path', 'method', 
                   'status_code', 'formatted_execution_time', 'timestamp')
    list_filter = ('method', 'status_code', 'timestamp', 'user')
    search_fields = ('path', 'user_token__key', 'user__email')
    readonly_fields = ('id', 'user', 'user_token', 'path', 'method', 
                      'status_code', 'execution_time', 'timestamp',
                      'formatted_request_body', 'formatted_response_body')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    list_per_page = 50
    
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Otimiza o queryset carregando relacionamentos.
        
        Melhora a performance ao carregar informações relacionadas aos logs,
        evitando múltiplas queries para user e user_token.
        
        Args:
            request: Requisição HTTP atual.
            
        Returns:
            QuerySet otimizado com related fields precarregados.
            
        Raises:
            ApplicationError: Se ocorrer erro ao processar a query.
        """
        try:
            return super().get_queryset(request).select_related(
                'user', 'user_token'
            )
        except Exception as e:
            logger.error(f"Erro ao carregar queryset de logs: {str(e)}", exc_info=True)
            messages.error(request, f"Erro ao carregar logs: {str(e)}")
            # Retorna um queryset vazio em caso de erro
            return APILog.objects.none()
    
    def has_add_permission(self, request: HttpRequest) -> bool:
        """Desabilita adição manual de logs.
        
        Os logs são gerados automaticamente pelo sistema, não devendo
        ser inseridos manualmente.
        
        Args:
            request: Requisição HTTP atual.
            
        Returns:
            bool: False, pois logs são gerados automaticamente.
        """
        return False
        
    def has_change_permission(self, request: HttpRequest, obj: Optional[Any] = None) -> bool:
        """Desabilita edição de logs.
        
        Logs não devem ser alterados após serem gerados para manter
        a integridade dos registros.
        
        Args:
            request: Requisição HTTP atual.
            obj: Objeto sendo editado, se houver.
            
        Returns:
            bool: False, pois logs não devem ser alterados.
        """
        return False
        
    def formatted_execution_time(self, obj: APILog) -> str:
        """Formata o tempo de execução com código de cores.
        
        Apresenta o tempo de execução em milissegundos com cores diferentes
        conforme a duração (verde para rápido, vermelho para lento).
        
        Args:
            obj: Instância de APILog sendo exibida.
            
        Returns:
            str: HTML formatado com o tempo colorido conforme a duração.
        """
        try:
            time_ms = obj.execution_time * 1000  # Converter para milissegundos
            
            if time_ms < 300:
                color = 'green'
            elif time_ms < 1000:
                color = 'orange'
            else:
                color = 'red'
                
            return format_html(
                '<span style="color: {};">{:.1f} ms</span>',
                color, time_ms
            )
        except Exception as e:
            logger.error(f"Erro ao formatar tempo de execução: {str(e)}")
            return str(obj.execution_time)
            
    formatted_execution_time.short_description = "Tempo (ms)"
    formatted_execution_time.admin_order_field = 'execution_time'

    def formatted_request_body(self, obj: APILog) -> str:
        """Formata o corpo da requisição para melhor visualização.
        
        Tenta detectar e formatar JSON para melhor apresentação,
        ou exibe o texto original caso não seja JSON válido.
        
        Args:
            obj: Instância de APILog sendo exibida.
            
        Returns:
            str: HTML formatado com o corpo da requisição.
        """
        if not obj.request_body:
            return "-"
            
        try:
            # Tenta identificar e formatar JSON
            data = json.loads(obj.request_body)
            formatted = json.dumps(data, indent=2)
            return format_html(
                '<pre style="max-height: 300px; overflow-y: auto;">{}</pre>',
                formatted
            )
        except json.JSONDecodeError:
            # Se não for JSON, retorna texto original
            return format_html(
                '<div style="max-height: 300px; overflow-y: auto; white-space: pre-wrap;">{}</div>',
                obj.request_body
            )
        except Exception as e:
            logger.error(f"Erro ao formatar corpo da requisição: {str(e)}")
            return f"Erro ao formatar corpo: {str(e)}"
            
    formatted_request_body.short_description = "Corpo da Requisição (formatado)"

    def formatted_response_body(self, obj: APILog) -> str:
        """Formata o corpo da resposta para melhor visualização.
        
        Tenta detectar e formatar JSON para melhor apresentação,
        ou exibe o texto original caso não seja JSON válido.
        
        Args:
            obj: Instância de APILog sendo exibida.
            
        Returns:
            str: HTML formatado com o corpo da resposta.
        """
        if not obj.response_body:
            return "-"
            
        try:
            # Tenta identificar e formatar JSON
            data = json.loads(obj.response_body)
            formatted = json.dumps(data, indent=2)
            return format_html(
                '<pre style="max-height: 300px; overflow-y: auto;">{}</pre>',
                formatted
            )
        except json.JSONDecodeError:
            # Se não for JSON, retorna texto original
            return format_html(
                '<div style="max-height: 300px; overflow-y: auto; white-space: pre-wrap;">{}</div>',
                obj.response_body
            )
        except Exception as e:
            logger.error(f"Erro ao formatar corpo da resposta: {str(e)}")
            return f"Erro ao formatar corpo: {str(e)}"
            
    formatted_response_body.short_description = "Corpo da Resposta (formatado)"