# accounts/admin.py

from django.contrib import admin
from .models import Profile, UserToken, AIClientConfiguration
from .forms import AIClientConfigurationForm

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved')
    list_editable = ('is_approved',)

class UserTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'key', 'created')
    list_filter = ('user', 'created')
    search_fields = ('user__email', 'name', 'key')

class AIClientConfigurationAdmin(admin.ModelAdmin):
    form = AIClientConfigurationForm  # Usa o formulário personalizado
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

admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserToken, UserTokenAdmin)
admin.site.register(AIClientConfiguration, AIClientConfigurationAdmin)
