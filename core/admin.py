from django.contrib import admin
from core.models.operations import Operation
from core.models.async_task_record import AsyncTaskRecord

@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ('operation_id', 'operation_type', 'user_token', 'created_at', 'expiration')
    search_fields = ('operation_id', 'operation_type', 'user_token__key')
    list_filter = ('operation_type', 'created_at', 'expiration')
    ordering = ('-created_at',)

@admin.register(AsyncTaskRecord)
class AsyncTaskRecordAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'operation', 'status', 'progress', 'created_at', 'updated_at')
    search_fields = ('task_id', 'operation__operation_id', 'status')
    list_filter = ('status', 'created_at', 'updated_at')
    ordering = ('-created_at',)
