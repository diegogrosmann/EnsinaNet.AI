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

from core.types.ai import AISuccess
from core.types.base import Result
from core.types.task import TaskStatus
from core.exceptions import AIConfigError, TrainingError, ApplicationError

from .models import ( 
    AIClientGlobalConfiguration, 
    AIClientConfiguration,
    AIFilesManager,
    AIModelsManager,
    AITraining,
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
            logger.error(f"Erro ao mascarar API key para {obj.name}: {e}", exc_info=True)
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
            raise AIConfigError(f"Erro ao salvar configuração: {str(e)}")

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
    list_display = ('name', 'user', 'uploaded_at')  # Removido train_all_a_is
    list_filter = ('uploaded_at', 'user')  # Adicionado filtro por usuário
    search_fields = ('name', 'user__email', 'user__username')  # Adicionado busca por email/username
    readonly_fields = ('uploaded_at',)
    
    def get_queryset(self, request):
        """Retorna o queryset dos arquivos de treinamento com user relacionado.
        
        Args:
            request: Requisição HTTP
            
        Returns:
            QuerySet: Conjunto de registros filtrados
        """
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
        """Retorna queryset otimizado com relacionamentos pré-carregados.
        
        Args:
            request: Requisição HTTP
            
        Returns:
            QuerySet: Conjunto de registros otimizado
        """
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
            logger.error(f"Erro ao gerar botão de arquivos: {e}", exc_info=True)
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
            logger.error(f"Erro ao gerar botão de modelos: {e}", exc_info=True)
            return "-"
    view_models_button.short_description = 'Modelos'
    
    def get_urls(self):
        """Define URLs customizadas para administração de modelos e arquivos.
        
        Returns:
            list: Lista de URLs
        """
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
        """View para listar arquivos de uma IA específica.
        
        Args:
            request: Requisição HTTP
            ai_config_id: ID da configuração da IA
            
        Returns:
            HttpResponse: Resposta com template renderizado
        """
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
            logger.error(f"Erro ao listar arquivos para IA {ai_config_id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao listar arquivos: {str(e)}')
            return redirect('..')
    
    def ai_models_list_view(self, request, ai_config_id):
        """View para listar modelos treinados de uma IA específica.
        
        Args:
            request: Requisição HTTP
            ai_config_id: ID da configuração da IA
            
        Returns:
            HttpResponse: Resposta com template renderizado
        """
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
            logger.error(f"Erro ao listar modelos para IA {ai_config_id}: {e}", exc_info=True)
            messages.error(request, f'Erro ao listar modelos: {str(e)}')
            return redirect('..')
    
    def delete_file_view(self, request, ai_config_id, file_id):
        """View para deletar um arquivo de treinamento.
        
        Args:
            request: Requisição HTTP
            ai_config_id: ID da configuração da IA
            file_id: ID do arquivo a ser excluído
            
        Returns:
            JsonResponse: Resposta com status da operação
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
            
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id)
        try:
            if ai_config.ai_client.delete_training_file(file_id):
                logger.info(f"Arquivo {file_id} excluído com sucesso por {request.user.username}")
                return JsonResponse({'success': True})
            logger.warning(f"Falha ao excluir arquivo {file_id}")
            return JsonResponse({'error': 'Não foi possível deletar o arquivo'}, status=400)
        except Exception as e:
            logger.error(f"Erro ao deletar arquivo {file_id}: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)
    
    def delete_model_view(self, request, ai_config_id, model_name):
        """View para deletar um modelo treinado.
        
        Args:
            request: Requisição HTTP
            ai_config_id: ID da configuração da IA
            model_name: Nome do modelo a ser excluído
            
        Returns:
            JsonResponse: Resposta com status da operação
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
            
        ai_config = get_object_or_404(AIClientConfiguration, id=ai_config_id)
        try:
            if ai_config.ai_client.delete_trained_model(model_name):
                logger.info(f"Modelo {model_name} excluído com sucesso por {request.user.username}")
                return JsonResponse({'success': True})
            logger.warning(f"Falha ao excluir modelo {model_name}")
            return JsonResponse({'error': 'Não foi possível deletar o modelo'}, status=400)
        except Exception as e:
            logger.error(f"Erro ao deletar modelo {model_name}: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)

class AIModelsAdmin(admin.ModelAdmin):
    """Interface administrativa para gerenciar modelos."""
    
    change_list_template = "admin/ai_config/models_manager.html"
    
    def has_add_permission(self, request):
        """Verifica se o usuário tem permissão para adicionar registros.
        
        Args:
            request: Requisição HTTP
            
        Returns:
            bool: Sempre False, pois não permitimos adição direta
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Verifica se o usuário tem permissão para excluir registros.
        
        Args:
            request: Requisição HTTP
            obj: Objeto a ser excluído ou None
            
        Returns:
            bool: Sempre False, pois usamos view customizada para exclusão
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """Verifica se o usuário tem permissão para editar registros.
        
        Args:
            request: Requisição HTTP
            obj: Objeto a ser editado ou None
            
        Returns:
            bool: Sempre False, pois esta interface é somente para visualização
        """
        return False
    
    def changelist_view(self, request, extra_context=None):
        """View customizada para listar os modelos disponíveis.
        
        Args:
            request: Requisição HTTP
            extra_context: Contexto adicional opcional
            
        Returns:
            HttpResponse: Resposta com template renderizado
        """
        # Obtém todas as configurações globais que implementam o método api_list_models
        global_configs = []
        for config in AIClientGlobalConfiguration.objects.all():
            try:
                client = config.create_api_client_instance()
                # Verifica se o cliente implementa o método api_list_models
                if hasattr(client, 'api_list_models'):
                    global_configs.append(config)
            except Exception as e:
                logger.warning(f"Erro ao verificar cliente {config.name}: {e}")
        
        context = {
            'title': 'Gerenciador de Modelos',
            'global_configs': global_configs,
            'selected_config': request.GET.get('ai_config'),
            **self.admin_site.each_context(request),
        }
        
        if request.GET.get('ai_config'):
            try:
                config = AIClientGlobalConfiguration.objects.get(id=request.GET['ai_config'])
                client = config.create_api_client_instance()
                
                if hasattr(client, 'api_list_models'):
                    # Obtém os modelos da API
                    models = client.api_list_models(list_trained_models=True, list_base_models=True)
                    
                    # Processa os modelos para adicionar informações de treinamento
                    formatted_models = []
                    for model in models:
                        model_data = {
                            'id': model.id,
                            'display_id': model.id,
                            'name': model.name,
                            'is_fine_tuned': model.is_fine_tuned,
                            'owner': None,
                            'training_id': None,
                            'training_status': None
                        }
                        
                        # Tenta encontrar um registro de treinamento associado a este modelo
                        if model.is_fine_tuned:
                            training = AITraining.objects.filter(model_name=model.id).first()
                            if training:
                                model_data['owner'] = training.ai_config.user.username
                                model_data['training_id'] = training.id
                                model_data['training_status'] = training.status
                        
                        formatted_models.append(model_data)
                    
                    context['models'] = formatted_models
                else:
                    messages.warning(request, 'Esta IA não suporta listagem de modelos.')
            except Exception as e:
                logger.error(f"Erro ao listar modelos: {e}", exc_info=True)
                messages.error(request, f'Erro ao listar modelos: {str(e)}')
        
        return TemplateResponse(request, self.change_list_template, context)

    def get_urls(self):
        """Define URLs customizadas para administração de modelos.
        
        Returns:
            list: Lista de URLs
        """
        urls = super().get_urls()
        custom_urls = [
            path('delete/', self.admin_site.admin_view(self.delete_models_view), name='delete_trained_models'),
        ]
        return custom_urls + urls
    
    def delete_models_view(self, request):
        """Deleta múltiplos modelos treinados e seus registros de treinamento.
        
        Args:
            request: Requisição HTTP
            
        Returns:
            JsonResponse: Resposta com status da operação
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
        
        config_id = request.POST.get('ai_config')
        model_ids = request.POST.getlist('model_names[]')
        
        if not config_id or not model_ids:
            return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
        
        config = get_object_or_404(AIClientGlobalConfiguration, id=config_id)
        
        errors = []
        success_count = 0
        
        try:
            for model_id in model_ids:
                try:
                    # Primeiro verifica se existe treinamento associado a este modelo
                    training = AITraining.objects.filter(model_name=model_id).first()
                    
                    if training and training.status != TaskStatus.COMPLETED.value:
                        errors.append(f"Não é possível excluir o modelo {model_id} porque o treinamento {training.id} ainda está em andamento.")
                        continue
                    
                    if training:
                        try:
                            id = training.id
                            training.delete()
                            logger.info(f"Registro de treinamento {id} excluído junto com o modelo {model_id}")
                        except Exception as e:
                            logger.error(f"Erro ao deletar registro de treinamento {training.id}: {e}", exc_info=True)
                            errors.append(f'Erro ao deletar registro de treinamento {training.id}: {str(e)}')
                            result = Result(success=False, error=str(e))
                    else:
                        client = config.create_api_client_instance()
                        # Tenta excluir o modelo da API
                        result = client.delete_trained_model(model_id)
                        logger.info(f"Modelo {model_id} excluído com sucesso")
                    
                    if result.success:
                        # Se o modelo foi excluído com sucesso, também exclui o registro de treinamento
                        if training:
                            training.delete()
                            logger.info(f"Registro de treinamento {training.id} excluído junto com o modelo {model_id}")
                        
                        success_count += 1
                    else:
                        errors.append(f'Não foi possível deletar o modelo {model_id}: {result.error}')
                except Exception as e:
                    logger.error(f"Erro ao deletar modelo {model_id}: {e}", exc_info=True)
                    errors.append(f'Erro ao deletar modelo {model_id}: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao criar cliente de API: {e}", exc_info=True)
            return JsonResponse({'error': f'Erro ao criar cliente de API: {str(e)}'}, status=500)
        
        return JsonResponse({
            'success': True,
            'deleted': success_count,
            'errors': errors
        })

class AIFilesAdmin(admin.ModelAdmin):
    """Interface administrativa para gerenciar arquivos de IA."""
    
    change_list_template = "admin/ai_config/files_manager.html"
    
    def has_add_permission(self, request):
        """Verifica se o usuário tem permissão para adicionar registros.
        
        Args:
            request: Requisição HTTP
            
        Returns:
            bool: Sempre False, pois não permitimos adição direta
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Verifica se o usuário tem permissão para excluir registros.
        
        Args:
            request: Requisição HTTP
            obj: Objeto a ser excluído ou None
            
        Returns:
            bool: Sempre False, pois usamos view customizada para exclusão
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """Verifica se o usuário tem permissão para editar registros.
        
        Args:
            request: Requisição HTTP
            obj: Objeto a ser editado ou None
            
        Returns:
            bool: Sempre False, pois esta interface é somente para visualização
        """
        return False
    
    def changelist_view(self, request, extra_context=None):
        """View customizada para listar os clientes de IA disponíveis.
        
        Args:
            request: Requisição HTTP
            extra_context: Contexto adicional opcional
            
        Returns:
            HttpResponse: Resposta com template renderizado
        """
        # Obtém todas as configurações globais que implementam o método api_list_files
        global_configs = []
        for config in AIClientGlobalConfiguration.objects.all():
            try:
                client = config.create_api_client_instance()
                # Verifica se o cliente implementa o método api_list_files
                if hasattr(client, 'api_list_files'):
                    global_configs.append(config)
            except Exception as e:
                logger.warning(f"Erro ao verificar cliente {config.name}: {e}")
        
        context = {
            'title': 'Arquivos na IA',
            'global_configs': global_configs,
            'selected_config': request.GET.get('ai_config'),
            **self.admin_site.each_context(request),
        }
        
        if request.GET.get('ai_config'):
            try:
                config = AIClientGlobalConfiguration.objects.get(id=request.GET['ai_config'])
                client = config.create_api_client_instance()
                if hasattr(client, 'api_list_files'):
                    files = client.api_list_files()
                    # Garantindo que cada arquivo tenha seu ID disponível para exibição
                    for file in files:
                        # Se o arquivo não tiver um atributo 'id' explícito, verificamos outros campos comuns
                        if not hasattr(file, 'id') and hasattr(file, 'file_id'):
                            file.id = file.file_id
                        # Adicionamos o id como um campo de exibição explícito para facilitar sua visualização no template
                        if hasattr(file, 'id'):
                            file.display_id = file.id
                    context['files'] = files
                else:
                    messages.warning(request, 'Esta IA não suporta listagem de arquivos.')
            except Exception as e:
                logger.error(f"Erro ao listar arquivos: {e}", exc_info=True)
                messages.error(request, f'Erro ao listar arquivos: {str(e)}')
        
        return TemplateResponse(request, self.change_list_template, context)

    def get_urls(self):
        """Define URLs customizadas para administração de arquivos.
        
        Returns:
            list: Lista de URLs
        """
        urls = super().get_urls()
        custom_urls = [
            path('delete/', self.admin_site.admin_view(self.delete_files_view), name='delete_files'),
        ]
        return custom_urls + urls
    
    def delete_files_view(self, request):
        """Deleta múltiplos arquivos de IA.
        
        Args:
            request: Requisição HTTP
            
        Returns:
            JsonResponse: Resposta com status da operação
        """
        if request.method != 'POST':
            return JsonResponse({'error': 'Método não permitido'}, status=405)
        
        config_id = request.POST.get('ai_config')
        file_ids = request.POST.getlist('file_ids[]')
        
        if not config_id or not file_ids:
            return JsonResponse({'error': 'Parâmetros inválidos'}, status=400)
        
        config = get_object_or_404(AIClientGlobalConfiguration, id=config_id)
        
        errors = []
        success_count = 0
        
        try:
            client = config.create_api_client_instance()
            for file_id in file_ids:
                try:
                    result = client.delete_file(file_id)
                    if result.success:
                        success_count += 1
                        logger.info(f"Arquivo {file_id} excluído com sucesso")
                    else:
                        logger.warning(f"Falha ao excluir arquivo {file_id}: {result.error}")
                        errors.append(f'Não foi possível deletar o arquivo {file_id}: {result.error}')
                except Exception as e:
                    logger.error(f"Erro ao deletar arquivo {file_id}: {e}", exc_info=True)
                    errors.append(f'Erro ao deletar arquivo {file_id}: {str(e)}')
        except Exception as e:
            logger.error(f"Erro ao criar cliente de API: {e}", exc_info=True)
            return JsonResponse({'error': f'Erro ao criar cliente de API: {str(e)}'}, status=500)
        
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
admin.site.register(AIFilesManager, AIFilesAdmin)
admin.site.register(AIModelsManager, AIModelsAdmin)
