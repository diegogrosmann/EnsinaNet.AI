"""Classes de administração para ai_config.

Define interfaces administrativas para gerenciar configurações globais de IA, 
configurações de clientes, arquivos de treinamento e modelos treinados.
"""

import logging
from typing import Any, Optional, Dict, List

from django.http import JsonResponse
from django.urls import path, reverse
from django.template.response import TemplateResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import admin, messages
from django.utils.html import format_html
from django.db import transaction
from django.http import HttpRequest, HttpResponse

from .models import ( 
    AIClientGlobalConfiguration, 
    AIClientConfiguration,
    AITrainedModelsManager,
    AITraining,
    AITrainingFilesManager, 
    TokenAIConfiguration, 
    AITrainingFile, 
    DoclingConfiguration,
)

from .forms import (
    AIClientGlobalConfigForm, 
    AIClientConfigurationForm, 
    TokenAIConfigurationForm, 
    AITrainingFileForm, 
)


logger = logging.getLogger(__name__)

class AIClientGlobalConfigAdmin(admin.ModelAdmin):
    """Administração das configurações globais dos clientes de IA.

    Permite gerenciar configurações globais que definem o comportamento base
    dos clientes de IA, incluindo chaves de API e URLs.
    """
    form = AIClientGlobalConfigForm
    list_display = ('name', 'api_client_class', 'api_url', 'masked_api_key')
    search_fields = ('name', 'api_client_class')
    list_filter = ('name',)

    def masked_api_key(self, obj: Any) -> str:
        """Retorna uma versão mascarada da chave de API.
        
        Args:
            obj: Objeto de configuração global.
            
        Returns:
            str: Chave mascarada ou string vazia.
        """
        try:
            if obj.api_key:
                if len(obj.api_key) > 8:
                    return f"{obj.api_key[:4]}****{obj.api_key[-4:]}"
                return '*' * len(obj.api_key)
            return ""
        except Exception as e:
            logger.error(f"Erro ao mascarar API key para {obj.name}: {e}")
            return "Erro ao mascarar chave"
    masked_api_key.short_description = 'API Key'

    def get_readonly_fields(self, request: HttpRequest, obj: Optional[Any] = None) -> tuple:
        """Define campos somente leitura durante a edição.
        
        Args:
            request: Requisição HTTP.
            obj: Objeto sendo editado ou None para criação.
            
        Returns:
            tuple: Lista de campos somente leitura.
        """
        # Em edição, api_client_class não pode ser alterada
        if obj:
            return self.readonly_fields + ('api_client_class',)
        return self.readonly_fields

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        """Salva o modelo com registro apropriado de logs.
        
        Args:
            request: Requisição HTTP.
            obj: Objeto sendo salvo.
            form: Formulário usado na operação.
            change: True se é edição, False se é criação.
        """
        try:
            with transaction.atomic():
                super().save_model(request, obj, form, change)
                action = "atualizada" if change else "criada"
                logger.info(
                    f"Configuração global '{obj.name}' {action} por {request.user.username}"
                )
        except Exception as e:
            logger.exception(f"Erro ao salvar configuração global '{obj.name}': {e}")
            raise

class AIClientConfigurationAdmin(admin.ModelAdmin):
    """Administração das configurações dos clientes de IA."""
    form = AIClientConfigurationForm
    list_display = ('name', 'ai_client')
    list_filter = ('name', 'ai_client')
    search_fields = ('ai_client__api_client_class', 'name')
    fields = ('name', 'ai_client', 'model_name', 'configurations')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customiza o queryset para o campo estrangeiro 'ai_client'.

        Args:
            db_field: Campo que está sendo processado.
            request: Requisição HTTP.
            kwargs: Argumentos adicionais.

        Returns:
            Campo modificado com o queryset adequado.
        """
        if db_field.name == "ai_client":
            # Agora não filtramos mais para limitar
            kwargs["queryset"] = AIClientGlobalConfiguration.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class TokenAIConfigurationAdmin(admin.ModelAdmin):
    """Administração da configuração TokenAI.

    Permite gerenciar os parâmetros de prompt para cada token.
    """
    form = TokenAIConfigurationForm
    list_display = ('token', 'base_instruction', 'prompt', 'responses')
    search_fields = ('token__name', 'token__user__email')
    list_filter = ('token',)

class AITrainingFileAdmin(admin.ModelAdmin):
    """Administração dos arquivos de treinamento.

    Configura a interface para upload, download e exclusão de arquivos.
    """
    form = AITrainingFileForm
    list_display = ('name', 'user', 'file', 'uploaded_at')  # Removido train_all_a_is
    list_filter = ('uploaded_at', 'user')  # Adicionado filtro por usuário
    search_fields = ('name', 'user__email', 'user__username')  # Adicionado busca por email/username
    readonly_fields = ('uploaded_at',)
    
    def get_queryset(self, request):
        """Retorna o queryset dos arquivos de treinamento com user relacionado."""
        return super().get_queryset(request).select_related('user')

class DoclingConfigurationAdmin(admin.ModelAdmin):
    """Administração da configuração Docling.

    Permite adicionar apenas uma instância do modelo.
    """
    def has_add_permission(self, request):
        """Permite adicionar apenas se não existir nenhuma configuração.

        Args:
            request: Requisição HTTP.

        Returns:
            bool: True se permitido adicionar, False caso contrário.
        """
        # Permite adicionar apenas se não existir nenhuma configuração
        if self.model.objects.exists():
            return False
        return True

class AITrainingAdmin(admin.ModelAdmin):
    """Administração dos treinamentos de IA."""
    list_display = ('ai_config', 'job_id', 'status', 'model_name', 'created_at', 
                   'view_files_button', 'view_models_button')
    list_filter = ('status', 'ai_config__ai_client__api_client_class')
    search_fields = ('job_id', 'model_name', 'ai_config__name')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request: HttpRequest) -> Any:
        """Retorna queryset otimizado com relacionamentos pré-carregados."""
        return AITraining.objects.all().select_related(
            'ai_config',
            'ai_config__ai_client',
            'file'
        ).order_by('-created_at')

    def view_files_button(self, obj: Any) -> str:
        """Gera HTML para botão de visualização de arquivos.
        
        Args:
            obj: Objeto de treinamento.
            
        Returns:
            str: HTML formatado do botão ou '-'.
        """
        try:
            if not obj.ai_config.ai_client.get_client_can_train():
                return "-"
            return format_html(
                '<a class="button" href="{}">Ver Arquivos</a>',
                reverse('admin:ai_files_list', args=[obj.ai_config.id])
            )
        except Exception as e:
            logger.error(f"Erro ao gerar botão de arquivos: {e}")
            return "-"
    view_files_button.short_description = 'Arquivos'

    def view_models_button(self, obj: Any) -> str:
        """Gera HTML para botão de visualização de modelos.
        
        Args:
            obj: Objeto de treinamento.
            
        Returns:
            str: HTML formatado do botão ou '-'.
        """
        try:
            if not obj.ai_config.ai_client.get_client_can_train():
                return "-"
            return format_html(
                '<a class="button" href="{}">Ver Modelos</a>',
                reverse('admin:ai_models_list', args=[obj.ai_config.id])
            )
        except Exception as e:
            logger.error(f"Erro ao gerar botão de modelos: {e}")
            return "-"
    view_models_button.short_description = 'Modelos'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ai/<int:ai_config_id>/files/',
                 self.admin_site.admin_view(self.ai_files_list_view),
                 name='ai_files_list'),
            path('ai/<int:ai_config_id>/models/',
                 self.admin_site.admin_view(self.ai_models_list_view),
                 name='ai_models_list'),
            path('ai/file/<int:ai_config_id>/delete/<str:file_id>/',
                 self.admin_site.admin_view(self.delete_file_view),
                 name='delete_ai_file'),
            path('ai/model/<int:ai_config_id>/delete/<str:model_name>/',
                 self.admin_site.admin_view(self.delete_model_view),
                 name='delete_ai_model'),
        ]
        return custom_urls + urls
    
    def ai_files_list_view(self, request, ai_config_id):
        """View para listar arquivos de uma IA específica."""
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id)
        try:
            files = ai_config.ai_client.list_files()
            
            context = {
                'ai_config': ai_config,
                'files': files,
                'opts': self.model._meta,
            }
            return TemplateResponse(request, 'admin/ai_config/training_files_list.html', context)
        except Exception as e:
            messages.error(request, f'Erro ao listar arquivos: {str(e)}')
            return redirect('..')
    
    def ai_models_list_view(self, request, ai_config_id):
        """View para listar modelos treinados de uma IA específica."""
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id)
        try:
            models = ai_config.ai_client.list_trained_models()
            
            # Formata os dados para o template
            formatted_models = []
            for model in models:
                formatted_models.append({
                    'name': model.get('name', 'N/A'),
                    'status': model.get('status', 'unknown'),
                    'created_at': model.get('created_at', None),
                    'error': model.get('error', ''),
                    'metadata': model.get('metadata', {})
                })
            
            context = {
                'ai_config': ai_config,
                'models': formatted_models,
                'opts': self.model._meta,
            }
            return TemplateResponse(request, 'admin/ai_config/models_list.html', context)
        except Exception as e:
            messages.error(request, f'Erro ao listar modelos: {str(e)}')
            return redirect('..')
    
    def delete_file_view(self, request, ai_config_id, file_id):
        """View para deletar um arquivo de treinamento."""
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
            
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id)
        try:
            if ai_config.ai_client.delete_training_file(file_id):
                return JsonResponse({'success': True})
            return JsonResponse({'error': 'Não foi possível deletar o arquivo'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def delete_model_view(self, request, ai_config_id, model_name):
        """View para deletar um modelo treinado."""
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
            
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id)
        try:
            if ai_config.ai_client.delete_trained_model(model_name):
                return JsonResponse({'success': True})
            return JsonResponse({'error': 'Não foi possível deletar o modelo'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class AITrainingFilesAdmin(admin.ModelAdmin):
    """Interface administrativa para gerenciar arquivos de treinamento."""
    
    change_list_template = "admin/ai_config/training_files_manager.html"
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """View customizada para listar os clientes de IA disponíveis."""
        # Obtém todas as configurações globais que suportam treinamento
        global_configs = []
        for config in AIClientGlobalConfiguration.objects.all():
            if config.get_client_can_train():
                global_configs.append(config)
        
        context = {
            'title': 'Arquivos de Treinamento na IA',
            'global_configs': global_configs,
            'selected_config': request.GET.get('ai_config'),
            **self.admin_site.each_context(request),
        }
        
        if request.GET.get('ai_config'):
            try:
                config = AIClientGlobalConfiguration.objects.get(id=request.GET['ai_config'])
                context['files'] = config.list_files()
            except Exception as e:
                messages.error(request, f'Erro ao listar arquivos: {str(e)}')
        
        return TemplateResponse(request, self.change_list_template, context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('delete/', self.admin_site.admin_view(self.delete_files_view), name='delete_training_files'),
        ]
        return custom_urls + urls
    
    def delete_files_view(self, request):
        """Deleta múltiplos arquivos de treinamento."""
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
        
        config_id = request.POST.get('ai_config')
        file_ids = request.POST.getlist('file_ids[]')
        
        if not config_id or not file_ids:
            return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
        
        config = get_object_or_404(AIClientGlobalConfiguration, id=config_id)
        
        errors = []
        success_count = 0
        
        for file_id in file_ids:
            try:
                if config.delete_training_file(file_id):
                    success_count += 1
                else:
                    errors.append(f'Não foi possível deletar o arquivo {file_id}')
            except Exception as e:
                errors.append(f'Erro ao deletar arquivo {file_id}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'deleted': success_count,
            'errors': errors
        })

class AITrainedModelsAdmin(admin.ModelAdmin):
    """Interface administrativa para gerenciar modelos treinados."""
    
    change_list_template = "admin/ai_config/models_manager.html"
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        # Obtém apenas configurações globais que suportam treinamento
        global_configs = []
        for config in AIClientGlobalConfiguration.objects.all():
            if config.get_client_can_train():
                global_configs.append(config)
        
        context = {
            'title': 'Gerenciador de Modelos Treinados',
            'global_configs': global_configs,
            'selected_config': request.GET.get('ai_config'),
            **self.admin_site.each_context(request),
        }
        
        if request.GET.get('ai_config'):
            try:
                config = AIClientGlobalConfiguration.objects.get(id=request.GET['ai_config'])
                
                if config.get_client_can_train():
                    models = config.list_trained_models()
                    context['models'] = models
                else:
                    messages.error(request, 'Esta IA não suporta treinamento.')
            except Exception as e:
                messages.error(request, f'Erro ao listar modelos: {str(e)}')
        
        return TemplateResponse(request, self.change_list_template, context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('delete/', self.admin_site.admin_view(self.delete_models_view), name='delete_trained_models'),
        ]
        return custom_urls + urls
    
    def delete_models_view(self, request):
        """Deleta múltiplos modelos treinados."""
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
        
        config_id = request.POST.get('ai_config')
        model_names = request.POST.getlist('model_names[]')
        
        if not config_id or not model_names:
            return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
        
        config = get_object_or_404(AIClientGlobalConfiguration, id=config_id)
        
        errors = []
        success_count = 0
        
        for model_name in model_names:
            try:
                if config.delete_trained_model(model_name):
                    success_count += 1
                else:
                    errors.append(f'Não foi possível deletar o modelo {model_name}')
            except Exception as e:
                errors.append(f'Erro ao deletar modelo {model_name}: {str(e)}')
        
        return JsonResponse({
            'success': True,
            'deleted': success_count,
            'errors': errors
        })

# Registra o admin
admin.site.register(AIClientGlobalConfiguration, AIClientGlobalConfigAdmin)
admin.site.register(AIClientConfiguration, AIClientConfigurationAdmin)
admin.site.register(TokenAIConfiguration, TokenAIConfigurationAdmin)
admin.site.register(AITrainingFile, AITrainingFileAdmin)
admin.site.register(DoclingConfiguration, DoclingConfigurationAdmin)
admin.site.register(AITrainingFilesManager, AITrainingFilesAdmin)
admin.site.register(AITrainedModelsManager, AITrainedModelsAdmin)
