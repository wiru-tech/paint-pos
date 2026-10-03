from django.contrib import admin

from .models import (
    PigmentStockLevel, PurchaseOrder, PurchaseOrderLine, StockLevel, StockTransfer, Supplier,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_name", "phone", "email", "default_discount_percentage", "is_active")
    list_display_links = ("name",)
    list_editable = ("default_discount_percentage", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_name", "email", "phone")


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "supplier", "branch", "status", "subtotal", "standard_discount",
        "manual_discount", "grand_total", "created_at",
    )
    list_filter = ("status", "supplier", "branch")
    search_fields = ("reference", "supplier__name")
    readonly_fields = ("subtotal", "standard_discount", "grand_total", "reference", "created_at")
    inlines = [PurchaseOrderLineInline]

    def save_related(self, request, form, formsets, change):
        # Lines (via the inline formset) and manual_discount are only saved by this
        # point, so recalculate here — subtotal/standard_discount/grand_total would
        # otherwise go stale whenever a line or the discount is edited from admin.
        super().save_related(request, form, formsets, change)
        form.instance.recalculate_totals()


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ("product", "branch", "quantity", "reorder_threshold", "status")
    list_filter = ("branch",)
    search_fields = ("product__sku", "product__name")

    @admin.display(description="Status")
    def status(self, obj):
        return obj.status


@admin.register(PigmentStockLevel)
class PigmentStockLevelAdmin(admin.ModelAdmin):
    list_display = ("pigment", "branch", "volume_ml")
    list_filter = ("branch",)
    search_fields = ("pigment__code", "pigment__name")


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ("product", "from_branch", "to_branch", "quantity", "status", "created_at")
    list_filter = ("status", "from_branch", "to_branch")
    search_fields = ("product__sku", "product__name")
