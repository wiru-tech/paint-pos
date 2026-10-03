from decimal import Decimal

from django.db import migrations


def backfill_totals(apps, schema_editor):
    PurchaseOrder = apps.get_model("inventory", "purchaseorder")
    cents = Decimal("0.01")
    for order in PurchaseOrder.objects.select_related("supplier").prefetch_related("lines"):
        subtotal = sum(
            (line.unit_cost * line.quantity_ordered for line in order.lines.all()), start=Decimal("0")
        ).quantize(cents)
        rate = order.supplier.default_discount_percentage or Decimal("0")
        standard_discount = (subtotal * rate / Decimal("100")).quantize(cents)
        grand_total = max(Decimal("0"), subtotal - standard_discount)
        order.subtotal = subtotal
        order.standard_discount = standard_discount
        order.grand_total = grand_total
        order.save(update_fields=["subtotal", "standard_discount", "grand_total"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0005_purchaseorder_grand_total_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_totals, noop),
    ]
