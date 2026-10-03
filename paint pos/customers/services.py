"""Loyalty points and store credit.

Rules (configurable in ``chromapos/settings.py``):

* ``LOYALTY_POINTS_PER_DOLLAR`` points are earned per whole dollar of a
  completed sale.
* ``LOYALTY_REDEEM_POINTS`` points can be redeemed for
  ``LOYALTY_REDEEM_CREDIT`` of store credit.

Every movement is written to :class:`~customers.models.LoyaltyEntry` so a
voided sale can be reversed cleanly and staff can see where credit came from.
"""
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import LoyaltyEntry


def points_per_dollar():
    return int(getattr(settings, "LOYALTY_POINTS_PER_DOLLAR", 1))


def redeem_block():
    return int(getattr(settings, "LOYALTY_REDEEM_POINTS", 100))


def redeem_credit():
    return Decimal(str(getattr(settings, "LOYALTY_REDEEM_CREDIT", "5.00")))


def points_for_total(total):
    """Whole points earned on a sale total."""
    return int(Decimal(total) * points_per_dollar())


@transaction.atomic
def award_points(customer, sale, user=None):
    """Give a customer their points for a completed sale."""
    if customer is None or customer.is_walkin:
        # Walk-ins are a name on a receipt, not a loyalty account.
        return None
    points = points_for_total(sale.total)
    if points <= 0:
        return None
    customer.loyalty_points += points
    customer.save(update_fields=["loyalty_points"])
    return LoyaltyEntry.objects.create(
        customer=customer, sale=sale, kind=LoyaltyEntry.KIND_EARN,
        points=points, note=f"Earned on {sale.invoice_number}", created_by=user,
    )


@transaction.atomic
def redeem_points(customer, blocks=1, user=None):
    """Convert points into store credit. Returns the credit granted."""
    blocks = max(1, int(blocks))
    cost = redeem_block() * blocks
    if customer.loyalty_points < cost:
        raise ValueError(
            f"{customer.name} has {customer.loyalty_points} points — "
            f"{cost} needed to redeem."
        )
    credit = redeem_credit() * blocks
    customer.loyalty_points -= cost
    customer.store_credit += credit
    customer.save(update_fields=["loyalty_points", "store_credit"])
    LoyaltyEntry.objects.create(
        customer=customer, kind=LoyaltyEntry.KIND_REDEEM,
        points=-cost, credit_delta=credit,
        note=f"Redeemed {cost} points for ${credit}", created_by=user,
    )
    return credit


@transaction.atomic
def spend_credit(customer, amount, sale=None, user=None):
    """Deduct store credit used as tender on a sale."""
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("Enter a store-credit amount greater than zero.")
    if customer.store_credit < amount:
        raise ValueError(f"{customer.name} only has ${customer.store_credit} in store credit.")
    customer.store_credit -= amount
    customer.save(update_fields=["store_credit"])
    LoyaltyEntry.objects.create(
        customer=customer, sale=sale, kind=LoyaltyEntry.KIND_SPEND,
        credit_delta=-amount, note="Store credit applied at checkout", created_by=user,
    )
    return amount


@transaction.atomic
def reverse_sale_entries(sale, user=None):
    """Undo points/credit tied to a sale (used when a sale is voided)."""
    entries = list(
        sale.loyalty_entries.exclude(kind=LoyaltyEntry.KIND_REVERSAL).select_related("customer")
    )
    if not entries:
        return []

    # A sale can carry more than one entry for the same customer (e.g. it both
    # earned points and spent store credit). Reuse one Customer instance per
    # customer so the adjustments accumulate instead of each entry's .save()
    # clobbering the last one with its own stale snapshot.
    customers = {}
    reversals = []
    for entry in entries:
        customer = customers.setdefault(entry.customer_id, entry.customer)
        customer.loyalty_points = max(0, customer.loyalty_points - entry.points)
        customer.store_credit -= entry.credit_delta
        if customer.store_credit < 0:
            customer.store_credit = Decimal("0.00")
        reversals.append(LoyaltyEntry(
            customer=customer, sale=sale, kind=LoyaltyEntry.KIND_REVERSAL,
            points=-entry.points, credit_delta=-entry.credit_delta,
            note=f"Reversed: {entry.get_kind_display()} on {sale.invoice_number}",
            created_by=user,
        ))

    for customer in customers.values():
        customer.save(update_fields=["loyalty_points", "store_credit"])
    return LoyaltyEntry.objects.bulk_create(reversals)
