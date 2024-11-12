# accounts/admin.py
import bleach
from django import forms
from django.conf import settings
from django.contrib import admin
from .models import Profile, UserToken, AIClientConfiguration, TokenConfiguration, DocumentAIConfiguration, GlobalConfiguration
from .forms import UserTokenForm, TokenConfigurationForm, AIClientConfigurationForm, GlobalConfigurationForm

from tinymce.widgets import TinyMCE

import os
import logging

logger = logging.getLogger(__name__)

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved')
    list_editable = ('is_approved',)

class UserTokenAdmin(admin.ModelAdmin):
    form = UserTokenForm
    list_display = ('name', 'key', 'user', 'created')
    search_fields = ('name', 'key', 'user__email')

class AIClientConfigurationAdmin(admin.ModelAdmin):
    form = AIClientConfigurationForm 
    list_display = ('api_client_class', 'model_name', 'masked_api_key')
    search_fields = ('api_client_class', 'model_name')
    list_filter = ('api_client_class',)

    def masked_api_key(self, obj):
        if obj.api_key:
            if len(obj.api_key) > 8:
                return f"{obj.api_key[:4]}****{obj.api_key[-4:]}"
            else:
                return '*' * len(obj.api_key)
        return ""
    masked_api_key.short_description = 'API Key'

class TokenConfigurationAdmin(admin.ModelAdmin):
    form = TokenConfigurationForm
    list_display = ('token', 'api_client_class', 'enabled')
    list_filter = ('api_client_class', 'enabled')
    search_fields = ('token__user__email', 'api_client_class')
    fields = ('token', 'api_client_class', 'enabled', 'model_name', 'configurations')

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
            # Obter o caminho completo a partir da variável de ambiente
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not credentials_path:
                raise forms.ValidationError('A variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não está definida.')

            full_path = os.path.join(settings.BASE_DIR, credentials_path)

            # Garantir que o diretório existe
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Salvar o arquivo no caminho fixo
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
        # Permitir apenas uma instância do modelo
        if DocumentAIConfiguration.objects.exists():
            return False
        return True

class GlobalConfigurationAdmin(admin.ModelAdmin):
    form = GlobalConfigurationForm
    list_display = ('__str__',)
    readonly_fields = ()

    def has_add_permission(self, request):
        if GlobalConfiguration.objects.exists():
            return False
        return True

    def base_instruction_preview(self, obj):
        return (obj.base_instruction[:75] + '...') if obj.base_instruction else 'Nenhuma'
    base_instruction_preview.short_description = 'Instrução Base'

    def prompt_preview(self, obj):
        return (obj.prompt[:75] + '...') if obj.prompt else 'Nenhuma'
    prompt_preview.short_description = 'Prompt'

    def responses_preview(self, obj):
        return (obj.responses[:75] + '...') if obj.responses else 'Nenhuma'
    responses_preview.short_description = 'Respostas'

admin.site.register(GlobalConfiguration, GlobalConfigurationAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserToken, UserTokenAdmin)
admin.site.register(AIClientConfiguration, AIClientConfigurationAdmin)
admin.site.register(TokenConfiguration, TokenConfigurationAdmin)
admin.site.register(DocumentAIConfiguration, DocumentAIConfigurationAdmin)
