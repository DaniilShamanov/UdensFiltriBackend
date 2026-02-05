from django.contrib import admin
from .models import Equipment, PlumbingCase, CaseMessage

class CaseMessageInline(admin.TabularInline):
    model = CaseMessage
    extra = 0
    readonly_fields=("created_at",)
    fields=("sender","message","is_internal","created_at")

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display=("name","manufacturer","model","user")
    search_fields=("name","manufacturer","model","serial_number","user__phone")

@admin.register(PlumbingCase)
class PlumbingCaseAdmin(admin.ModelAdmin):
    list_display=("title","user","status","priority","created_at")
    list_filter=("status","priority")
    search_fields=("title","description","user__phone")
    inlines=[CaseMessageInline]

@admin.register(CaseMessage)
class CaseMessageAdmin(admin.ModelAdmin):
    list_display=("case","sender","is_internal","created_at")
    list_filter=("is_internal",)
