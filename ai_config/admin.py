import bleach
import os
import logging

from django.contrib import admin
from django import forms
from django.conf import settings
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import admin, messages
from django.utils.html import format_html

from tinymce.widgets import TinyMCE

from .models import AIClient, AIClientConfiguration, TokenAIConfiguration, AITrainingFile, AIClientTraining, DocumentAIConfiguration
from .forms import AIClientForm, AIClientConfigurationForm, TokenAIConfigurationForm, AITrainingFileForm, AIClientTrainingForm

from .utils import perform_training

from api.utils.clientsIA import AVAILABLE_AI_CLIENTS

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

class AIClientAdmin(admin.ModelAdmin):
    form = AIClientForm
    list_display = ('api_client_class', 'masked_api_key')
    search_fields = ('api_client_class',)
    list_filter = ('api_client_class',)

    def masked_api_key(self, obj):
        if obj.api_key:
            if len(obj.api_key) > 8:
                return f"{obj.api_key[:4]}****{obj.api_key[-4:]}"
            else:
                return '*' * len(obj.api_key)
        return ""
    masked_api_key.short_description = 'API Key'

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Se 'obj' não for None, é uma edição
            return self.readonly_fields + ('api_client_class',)
        return self.readonly_fields

    def has_add_permission(self, request):
        existing_clients = AIClient.objects.values_list('api_client_class', flat=True)
        all_ai_classes = [client.name for client in AVAILABLE_AI_CLIENTS]
        missing_clients = set(all_ai_classes) - set(existing_clients)
        if not missing_clients:
            return False  # Desabilita o botão 'Adicionar'
        return True

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not obj:  # Se estiver criando uma nova instância
            existing_clients = AIClient.objects.values_list('api_client_class', flat=True)
            available_choices = [(client.name, client.name) for client in AVAILABLE_AI_CLIENTS if client.name not in existing_clients]
            form.base_fields['api_client_class'].choices = available_choices
        return form

class AIClientConfigurationAdmin(admin.ModelAdmin):  # Atualizado
    form = AIClientConfigurationForm
    list_display = ('token', 'ai_client', 'enabled')
    list_filter = ('ai_client', 'enabled')
    search_fields = ('token__user__email', 'ai_client__api_client_class')
    fields = ('token', 'ai_client', 'enabled', 'model_name', 'configurations')
    inlines = [AIClientTrainingInline]

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
            # Implementação da lógica de treinamento
            results = perform_training()  # Certifique-se de que esta função está correta
            for key, result in results.items():
                token_name, ai_name = key
                messages.info(request, f"Token {token_name}, {ai_name}: {result}")
            return redirect('..')
        context = {
            'training_file': training_file,
            'opts': self.model._meta,
            'title': 'Confirmar Treinamento das IAs',
        }
        return TemplateResponse(request, 'admin/ai_config/train_a_is_confirmation.html', context)

class AIClientTrainingAdmin(admin.ModelAdmin):
    form = AIClientTrainingForm
    list_display = ('ai_client_configuration', 'trained_model_name') 
    readonly_fields = ('trained_model_name',)

class DocumentAIConfigurationForm(forms.ModelForm):
    credentials_file = forms.FileField(
        required=False,
        label='Upload Credentials JSON',
        help_text='Faça o upload do arquivo JSON das credenciais do DocumentAI.'
    )

    class Meta:
        model = DocumentAIConfiguration
        fields = ['project_id', 'location', 'processor_id', 'credentials_file']

    def save(self, commit=True):
        instance = super().save(commit=False)
        credentials_file = self.cleaned_data.get('credentials_file')

        if credentials_file:
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not credentials_path:
                raise forms.ValidationError('A variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não está definida.')

            full_path = os.path.join(settings.BASE_DIR, credentials_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, 'wb+') as destination:
                for chunk in credentials_file.chunks():
                    destination.write(chunk)

            logger.info(f"Arquivo de credenciais do DocumentAI salvo em: {full_path}")

        if commit:
            instance.save()
        return instance

class DocumentAIConfigurationAdmin(admin.ModelAdmin):
    form = DocumentAIConfigurationForm
    list_display = ('project_id', 'location', 'processor_id')
    readonly_fields = ()  # Nenhum campo somente leitura

    def has_add_permission(self, request):
        if DocumentAIConfiguration.objects.exists():
            return False
        return True

admin.site.register(AIClient, AIClientAdmin)
admin.site.register(AIClientConfiguration, AIClientConfigurationAdmin)
admin.site.register(TokenAIConfiguration, TokenAIConfigurationAdmin)
admin.site.register(AITrainingFile, AITrainingFileAdmin)
admin.site.register(AIClientTraining, AIClientTrainingAdmin)
admin.site.register(DocumentAIConfiguration, DocumentAIConfigurationAdmin)
