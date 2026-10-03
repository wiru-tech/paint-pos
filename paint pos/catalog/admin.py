from django.contrib import admin

from .models import Brand, Category, ColorFormula, ColorFormulaLine, Pigment, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "brand", "unit_label", "unit_price", "is_tintable", "is_active")
    list_filter = ("category", "brand", "is_tintable", "is_active")
    search_fields = ("sku", "name")


@admin.register(Pigment)
class PigmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "hex_color", "cost_per_ml")
    search_fields = ("code", "name")


class ColorFormulaLineInline(admin.TabularInline):
    model = ColorFormulaLine
    extra = 1


@admin.register(ColorFormula)
class ColorFormulaAdmin(admin.ModelAdmin):
    list_display = ("name", "hex_color", "base_product", "base_size", "finish", "created_at")
    list_filter = ("base_size", "finish")
    search_fields = ("name", "hex_color")
    inlines = [ColorFormulaLineInline]
