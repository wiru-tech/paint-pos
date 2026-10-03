from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from inventory.models import StockLevel

from .models import Sale

class VoidError(Exception):
    """Raised when a sale cannot be voided."""


TINT_MARKUP_MULTIPLIER = Decimal("5")
TINT_MINIMUM_SURCHARGE = Decimal("5.00")


def get_open_sale(user):
    sale = (
        Sale.objects.filter(cashier=user, status=Sale.STATUS_OPEN)
        .order_by("-created_at")
        .first()
    )
    if sale is None:
        branch = getattr(getattr(user, "profile", None), "branch", None)
        sale = Sale.objects.create(cashier=user, branch=branch, status=Sale.STATUS_OPEN)
    return sale


def estimate_surcharge(pigment_volume_pairs):
    """pigment_volume_pairs: iterable of (pigment, volume_ml)."""
    pigment_cost = sum(
        (volume_ml * pigment.cost_per_ml for pigment, volume_ml in pigment_volume_pairs),
        start=Decimal("0"),
    )
    surcharge = (pigment_cost * TINT_MARKUP_MULTIPLIER).quantize(Decimal("0.01"))
    return max(surcharge, TINT_MINIMUM_SURCHARGE)


def tint_surcharge(formula):
    return estimate_surcharge((line.pigment, line.volume_ml) for line in formula.lines.all())


def pigment_cost(formula):
    """Raw colorant cost of a mix — what the pigments actually cost us."""
    return sum(
        (line.volume_ml * line.pigment.cost_per_ml for line in formula.lines.all()),
        start=Decimal("0"),
    ).quantize(Decimal("0.01"))


def tint_unit_cost(base_product, formula):
    """Cost of one tinted can: the base can plus the colorant that went in it."""
    base_cost = base_product.cost_price if base_product else Decimal("0")
    return (base_cost + pigment_cost(formula)).quantize(Decimal("0.01"))


@transaction.atomic
def finalize_sale(sale, user=None):
    """Close a paid sale: draw down stock, award loyalty, alert on shortages."""
    from customers.services import award_points
    from inventory.services import check_low_stock

    touched_levels = []
    for item in sale.items.select_related("product"):
        if item.product_id:
            stock, _ = StockLevel.objects.get_or_create(
                branch=sale.branch,
                product=item.product,
                defaults={"reorder_threshold": item.product.reorder_threshold},
            )
            stock.quantity = max(0, stock.quantity - int(item.quantity))
            stock.save(update_fields=["quantity"])
            touched_levels.append(stock)

    sale.status = Sale.STATUS_COMPLETED
    sale.completed_at = timezone.now()
    sale.save(update_fields=["status", "completed_at"])

    if sale.customer_id:
        award_points(sale.customer, sale, user=user)

    check_low_stock(touched_levels)
    return sale


@transaction.atomic
def void_sale(sale, user=None, reason=""):
    """Reverse a completed sale: restock the items and undo loyalty movements."""
    from customers.services import reverse_sale_entries

    if sale.status != Sale.STATUS_COMPLETED:
        raise VoidError("Only completed sales can be voided.")

    for item in sale.items.select_related("product"):
        if item.product_id:
            stock, _ = StockLevel.objects.get_or_create(
                branch=sale.branch,
                product=item.product,
                defaults={"reorder_threshold": item.product.reorder_threshold},
            )
            stock.quantity += int(item.quantity)
            stock.save(update_fields=["quantity"])

    reverse_sale_entries(sale, user=user)

    sale.status = Sale.STATUS_VOID
    sale.voided_at = timezone.now()
    sale.voided_by = user
    sale.void_reason = reason
    sale.save(update_fields=["status", "voided_at", "voided_by", "void_reason"])
    return sale
