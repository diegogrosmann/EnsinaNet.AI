from django import forms
from django.contrib import admin
from .models import Profile, UserToken
import logging

logger = logging.getLogger(__name__)

class ProfileAdmin(admin.ModelAdmin):
    """Administração para o modelo Profile.

    Configura a interface administrativa para gerenciamento de perfis de usuários.

    Attributes:
        list_display (tuple): Campos exibidos na listagem de perfis.
        list_editable (tuple): Campos editáveis diretamente na listagem.
    """
    list_display = ('user', 'is_approved')
    list_editable = ('is_approved',)

    def save_model(self, request, obj, form, change):
        """Salva o modelo e registra a operação nos logs.

        Args:
            request (HttpRequest): Objeto de requisição.
            obj (Profile): Instância do perfil.
            form (Form): Formulário utilizado.
            change (bool): Indica se é uma edição (True) ou criação (False).
        """
        try:
            action = "atualizado" if change else "criado"
            logger.info(f"Perfil de {obj.user.email} {action} pelo admin {request.user.email}")
            super().save_model(request, obj, form, change)
        except Exception as e:
            logger.error(f"Erro ao salvar perfil de {obj.user.email}: {str(e)}", exc_info=True)
            raise

class UserTokenAdmin(admin.ModelAdmin):
    """Administração para o modelo UserToken.

    Configura a interface administrativa para gerenciamento de tokens de autenticação.

    Attributes:
        form: Formulário utilizado para edição dos tokens.
        list_display (tuple): Campos exibidos na listagem de tokens.
        search_fields (tuple): Campos utilizados para pesquisa.
    """
    form = forms.ModelForm
    list_display = ('name', 'key', 'user', 'created')
    search_fields = ('name', 'key', 'user__email')

    def save_model(self, request, obj, form, change):
        """Salva o modelo e registra a operação nos logs.

        Args:
            request (HttpRequest): Objeto de requisição.
            obj (UserToken): Instância do token.
            form (Form): Formulário utilizado.
            change (bool): Indica se é edição (True) ou criação (False).
        """
        try:
            action = "atualizado" if change else "criado"
            logger.info(f"Token '{obj.name}' de {obj.user.email} {action} pelo admin {request.user.email}")
            super().save_model(request, obj, form, change)
        except Exception as e:
            logger.error(f"Erro ao salvar token '{obj.name}': {str(e)}", exc_info=True)
            raise

    def delete_model(self, request, obj):
        """Remove o modelo e registra a operação nos logs.

        Args:
            request (HttpRequest): Objeto de requisição.
            obj (UserToken): Instância do token a ser removido.
        """
        try:
            logger.info(f"Token '{obj.name}' de {obj.user.email} removido pelo admin {request.user.email}")
            super().delete_model(request, obj)
        except Exception as e:
            logger.error(f"Erro ao remover token '{obj.name}': {str(e)}", exc_info=True)
            raise

admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserToken, UserTokenAdmin)
