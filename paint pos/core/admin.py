from django.contrib import admin

from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_warehouse", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_warehouse", "is_active")
