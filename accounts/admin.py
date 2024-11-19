import bleach
from django import forms
from django.conf import settings
from django.contrib import admin
from .models import Profile, UserToken

from tinymce.widgets import TinyMCE

import os
import logging

logger = logging.getLogger(__name__)


class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved')
    list_editable = ('is_approved',)


class UserTokenAdmin(admin.ModelAdmin):
    form = forms.ModelForm 
    list_display = ('name', 'key', 'user', 'created')
    search_fields = ('name', 'key', 'user__email')


admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserToken, UserTokenAdmin)
