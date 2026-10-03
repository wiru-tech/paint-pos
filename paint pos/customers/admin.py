from django.contrib import admin

from .models import Customer, SavedFormula


class SavedFormulaInline(admin.TabularInline):
    model = SavedFormula
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "is_pro", "store_credit", "favorite_brand")
    list_filter = ("is_pro", "favorite_brand")
    search_fields = ("name", "phone", "email")
    inlines = [SavedFormulaInline]


@admin.register(SavedFormula)
class SavedFormulaAdmin(admin.ModelAdmin):
    list_display = ("reference_code", "customer", "color_formula", "finish", "created_at")
    list_filter = ("finish",)
    search_fields = ("reference_code", "customer__name", "color_formula__name")
