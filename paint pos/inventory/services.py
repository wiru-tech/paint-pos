"""Inventory business rules kept out of the views.

Covers the transfer approval workflow, stock adjustments, purchase-order
receiving and the low-stock alerting that feeds in-app notifications.
"""
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from core.models import Notification
from core.notifications import notify_managers

from .models import PurchaseOrder, StockAdjustment, StockLevel, StockTransfer


class TransferError(Exception):
    """Raised when a transfer cannot be applied (e.g. not enough stock)."""


def get_or_create_level(branch, product):
    level, _ = StockLevel.objects.get_or_create(
        branch=branch, product=product,
        defaults={"reorder_threshold": product.reorder_threshold},
    )
    return level


# --------------------------------------------------------------------------
# Low-stock alerting
# --------------------------------------------------------------------------

def check_low_stock(levels, *, email=False):
    """Raise a notification for each level at/below its reorder threshold.

    ``dedupe`` keeps a second alert from firing while the first is unread, so
    a busy day doesn't bury the cashier's other notifications.
    """
    created = 0
    for level in levels:
        if level.quantity > level.reorder_threshold:
            continue
        out = level.quantity == 0
        title = (
            f"Out of stock: {level.product.name}" if out
            else f"Low stock: {level.product.name}"
        )
        message = (
            f"{level.product.sku} at {level.branch.name} is down to "
            f"{level.quantity} unit(s) (reorder at {level.reorder_threshold})."
        )
        created += len(notify_managers(
            level.branch, title, message,
            level=Notification.LEVEL_CRITICAL if out else Notification.LEVEL_WARNING,
            url=f"{reverse('inventory:list')}?q={level.product.sku}",
            category="low_stock",
            dedupe=True,
            email=email,
        ))
    return created


def scan_low_stock(branch=None, *, email=False):
    """Sweep every stock level (optionally one branch) and alert on shortages."""
    qs = StockLevel.objects.select_related("product", "branch").filter(
        product__is_active=True, quantity__lte=F("reorder_threshold")
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    return check_low_stock(qs, email=email)


# --------------------------------------------------------------------------
# Transfers
# --------------------------------------------------------------------------

@transaction.atomic
def apply_transfer(transfer, user=None, note=""):
    """Move the stock and mark the transfer completed."""
    if transfer.status == StockTransfer.STATUS_COMPLETED:
        raise TransferError("This transfer has already been completed.")
    if transfer.status == StockTransfer.STATUS_CANCELLED:
        raise TransferError("This transfer was cancelled.")

    from_level = get_or_create_level(transfer.from_branch, transfer.product)
    if from_level.quantity < transfer.quantity:
        raise TransferError(
            f"{transfer.from_branch.name} only has {from_level.quantity} units of "
            f"{transfer.product.name} — cannot transfer {transfer.quantity}."
        )
    to_level = get_or_create_level(transfer.to_branch, transfer.product)

    from_level.quantity -= transfer.quantity
    from_level.save(update_fields=["quantity"])
    to_level.quantity += transfer.quantity
    to_level.save(update_fields=["quantity"])

    transfer.status = StockTransfer.STATUS_COMPLETED
    transfer.decided_by = user
    transfer.decided_at = timezone.now()
    if note:
        transfer.decision_note = note
    transfer.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])

    check_low_stock([from_level])
    return transfer


def reject_transfer(transfer, user=None, note=""):
    if not transfer.is_pending:
        raise TransferError("Only pending transfers can be rejected.")
    transfer.status = StockTransfer.STATUS_CANCELLED
    transfer.decided_by = user
    transfer.decided_at = timezone.now()
    transfer.decision_note = note
    transfer.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    return transfer


def request_transfer(*, product, from_branch, to_branch, quantity, user, note=""):
    """Create a pending transfer and ping the source branch's managers."""
    transfer = StockTransfer.objects.create(
        product=product, from_branch=from_branch, to_branch=to_branch,
        quantity=quantity, status=StockTransfer.STATUS_PENDING,
        created_by=user, note=note,
    )
    notify_managers(
        from_branch,
        f"Transfer request: {quantity} x {product.name}",
        f"{getattr(user, 'username', 'A staff member')} requested {quantity} unit(s) of "
        f"{product.sku} from {from_branch.name} to {to_branch.name}.",
        level=Notification.LEVEL_WARNING,
        url=reverse("inventory:transfer_list"),
        category="transfer",
    )
    return transfer


# --------------------------------------------------------------------------
# Adjustments
# --------------------------------------------------------------------------

@transaction.atomic
def adjust_stock(*, branch, product, new_quantity, reason, note="", user=None):
    level = get_or_create_level(branch, product)
    adjustment = StockAdjustment.objects.create(
        branch=branch, product=product,
        previous_quantity=level.quantity, new_quantity=new_quantity,
        reason=reason, note=note, created_by=user,
    )
    level.quantity = new_quantity
    level.save(update_fields=["quantity"])
    check_low_stock([level])
    return adjustment


# --------------------------------------------------------------------------
# Purchase orders
# --------------------------------------------------------------------------

@transaction.atomic
def receive_purchase_order(order, received_quantities, user=None):
    """Book received units into the ordering branch's stock.

    ``received_quantities`` maps line id -> quantity received in this batch.
    An order is marked received once every line is fully accounted for.
    """
    if order.status in (PurchaseOrder.STATUS_RECEIVED, PurchaseOrder.STATUS_CANCELLED):
        raise TransferError("This purchase order is already closed.")

    for line in order.lines.select_related("product"):
        qty = int(received_quantities.get(line.id, 0) or 0)
        if qty <= 0:
            continue
        level = get_or_create_level(order.branch, line.product)
        level.quantity += qty
        level.save(update_fields=["quantity"])
        line.quantity_received += qty
        line.save(update_fields=["quantity_received"])

    fully_received = all(
        line.quantity_received >= line.quantity_ordered
        for line in order.lines.order_by("id")
    )
    if fully_received:
        order.status = PurchaseOrder.STATUS_RECEIVED
        order.received_at = timezone.now()
        order.save(update_fields=["status", "received_at"])
    elif order.status == PurchaseOrder.STATUS_DRAFT:
        order.status = PurchaseOrder.STATUS_ORDERED
        order.ordered_at = order.ordered_at or timezone.now()
        order.save(update_fields=["status", "ordered_at"])
    return order


def build_reorder_suggestions(branch, limit=50):
    """Products at/below threshold at ``branch``, with a suggested top-up."""
    levels = (
        StockLevel.objects.filter(branch=branch, product__is_active=True,
                                  quantity__lte=F("reorder_threshold"))
        .select_related("product")
        .order_by("quantity")[:limit]
    )
    suggestions = []
    for level in levels:
        target = max(level.reorder_threshold * 2, level.reorder_threshold + 1)
        suggestions.append({
            "product": level.product,
            "quantity": level.quantity,
            "threshold": level.reorder_threshold,
            "suggested": max(1, target - level.quantity),
        })
    return suggestions
