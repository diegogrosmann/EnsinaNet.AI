from django.contrib import admin
from .models import Profile, UserToken

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved')
    list_editable = ('is_approved',)

class UserTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'key', 'created')
    list_filter = ('user', 'created')
    search_fields = ('user__email', 'name', 'key')

admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserToken, UserTokenAdmin)
