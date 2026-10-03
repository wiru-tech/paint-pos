from django.contrib import admin

from .models import Payment, Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "branch", "customer", "cashier", "status", "total", "created_at")
    list_filter = ("status", "branch")
    search_fields = ("invoice_number", "customer__name")
    inlines = [SaleItemInline, PaymentInline]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "description", "quantity", "unit_price", "line_total")
    search_fields = ("description", "sale__invoice_number")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("sale", "method", "amount", "tendered", "change_due", "created_at")
    list_filter = ("method",)
