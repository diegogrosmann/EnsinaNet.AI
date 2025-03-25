from django.contrib import admin
from .models import ClientVersion

@admin.register(ClientVersion)
class ClientVersionAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'version', 'release_date', 'is_mandatory', 'active')
    list_filter = ('product_name', 'is_mandatory', 'active')
    search_fields = ('product_name', 'version', 'release_notes')
    date_hierarchy = 'release_date'
