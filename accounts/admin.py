from django import forms
from django.contrib import admin
from .models import Profile, UserToken

import logging

logger = logging.getLogger(__name__)


class ProfileAdmin(admin.ModelAdmin):
    """Administração para o model Profile.
    
    Atributos:
        list_display (tuple): Campos exibidos na lista.
        list_editable (tuple): Campos editáveis diretamente na lista.
    """
    list_display = ('user', 'is_approved')
    list_editable = ('is_approved',)


class UserTokenAdmin(admin.ModelAdmin):
    """Administração para o model UserToken.
    
    Atributos:
        form: Formulário utilizado.
        list_display (tuple): Campos exibidos na lista.
        search_fields (tuple): Campos que podem ser pesquisados.
    """
    form = forms.ModelForm 
    list_display = ('name', 'key', 'user', 'created')
    search_fields = ('name', 'key', 'user__email')


admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserToken, UserTokenAdmin)
