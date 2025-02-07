import os
import logging

from django import forms
from django.conf import settings
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import admin, messages
from django.utils.html import format_html

from tinymce.widgets import TinyMCE

from api.utils.clientsIA import AI_CLIENT_MAPPING

from .models import ( 
    AIClientGlobalConfiguration, 
    AIClientConfiguration, 
    TokenAIConfiguration, 
    AITrainingFile, 
    AIClientTraining,
    DoclingConfiguration
)
from .forms import (
    AIClientGlobalConfigForm, 
    AIClientConfigurationForm, 
    TokenAIConfigurationForm, 
    AITrainingFileForm, 
    AIClientTrainingForm
)


from .utils import perform_training

logger = logging.getLogger(__name__)

class AIClientTrainingInline(admin.StackedInline):
    model = AIClientTraining
    form = AIClientTrainingForm
    extra = 0
    can_delete = True
    verbose_name = "Parâmetros de Treinamento de IA"
    verbose_name_plural = "Parâmetros de Treinamento de IA"
    fields = ['training_parameters', 'trained_model_name']
    readonly_fields = ['trained_model_name']

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        return formset

class AIClientGlobalConfigAdmin(admin.ModelAdmin):
    """
    Removemos o método has_add_permission original que impedia criar 
    múltiplas instâncias da mesma 'api_client_class'. Agora podemos 
    criar quantas quisermos.
    """
    form = AIClientGlobalConfigForm
    list_display = ('name', 'api_client_class', 'api_url', 'masked_api_key')
    search_fields = ('name', 'api_client_class')
    list_filter = ('name',)

    def masked_api_key(self, obj):
        if obj.api_key:
            if len(obj.api_key) > 8:
                return f"{obj.api_key[:4]}****{obj.api_key[-4:]}"
            else:
                return '*' * len(obj.api_key)
        return ""
    masked_api_key.short_description = 'API Key'

    # Removido o método "has_add_permission" que checava se ainda faltava algum AIClientType.
    # Agora é permitido adicionar vários registros para a mesma classe de IA.

    def get_readonly_fields(self, request, obj=None):
        # Você pode manter este comportamento ou remover, dependendo da sua necessidade:
        if obj:  # Se 'obj' não for None, é edição
            return self.readonly_fields + ('api_client_class',)
        return self.readonly_fields

class AIClientConfigurationAdmin(admin.ModelAdmin):
    form = AIClientConfigurationForm
    list_display = ('token', 'name', 'ai_client', 'enabled')
    list_filter = ('name', 'ai_client', 'enabled')
    search_fields = ('token__user__email', 'ai_client__api_client_class', 'name')
    fields = ('token', 'name', 'ai_client', 'enabled', 'model_name', 'configurations')
    inlines = [AIClientTrainingInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "ai_client":
            # Agora não filtramos mais para limitar
            kwargs["queryset"] = AIClientGlobalConfiguration.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class TokenAIConfigurationAdmin(admin.ModelAdmin):
    form = TokenAIConfigurationForm
    list_display = ('token', 'base_instruction', 'prompt', 'responses')
    search_fields = ('token__name', 'token__user__email')
    list_filter = ('token',)

class AITrainingFileAdmin(admin.ModelAdmin):
    form = AITrainingFileForm
    list_display = ('name', 'file', 'uploaded_at', 'train_all_a_is')
    list_filter = ('uploaded_at',)
    search_fields = ('name', 'user__email')
    readonly_fields = ('uploaded_at',)
    
    def train_all_a_is(self, obj):
        return format_html('<a class="button" href="{}">Treinar IAs</a>', f'train_a_is/{obj.id}/')
    train_all_a_is.short_description = 'Treinar todas as IAs'
    train_all_a_is.allow_tags = True
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('train_a_is/<int:training_file_id>/', self.admin_site.admin_view(self.train_a_is_view), name='train_a_is'),
        ]
        return custom_urls + urls
    
    def train_a_is_view(self, request, training_file_id):
        training_file = get_object_or_404(AITrainingFile, id=training_file_id)
        if request.method == 'POST':
            # Filtra apenas IAs que suportam treinamento
            trainable_ias = [
                name for name, client_class in AI_CLIENT_MAPPING.items()
                if client_class.can_train
            ]
            results = perform_training(request.user, training_file.token, trainable_ias)
            
            for ai_name, result in results.items():
                messages.info(request, f"{ai_name}: {result}")
            return redirect('..')

        context = {
            'training_file': training_file,
            'opts': self.model._meta,
            'title': 'Confirmar Treinamento das IAs',
            'trainable_ias': [
                name for name, client_class in AI_CLIENT_MAPPING.items()
                if client_class.can_train
            ]
        }
        return TemplateResponse(
            request, 
            'admin/ai_config/train_a_is_confirmation.html', 
            context
        )

class AIClientTrainingAdmin(admin.ModelAdmin):
    form = AIClientTrainingForm
    list_display = ('ai_client_configuration', 'trained_model_name') 
    readonly_fields = ('trained_model_name',)
    
class DoclingConfigurationAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Permite adicionar apenas se não existir nenhuma configuração
        if self.model.objects.exists():
            return False
        return True

admin.site.register(AIClientGlobalConfiguration, AIClientGlobalConfigAdmin)
admin.site.register(AIClientConfiguration, AIClientConfigurationAdmin)
admin.site.register(TokenAIConfiguration, TokenAIConfigurationAdmin)
admin.site.register(AITrainingFile, AITrainingFileAdmin)
admin.site.register(AIClientTraining, AIClientTrainingAdmin)
admin.site.register(DoclingConfiguration, DoclingConfigurationAdmin)
