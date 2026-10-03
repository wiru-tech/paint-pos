from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import ColorFormula, Product
from core.models import Branch
from customers.models import Customer

TAX_RATE = Decimal("0.08")

DISCOUNT_NONE = "none"
DISCOUNT_PERCENT = "percent"
DISCOUNT_AMOUNT = "amount"
DISCOUNT_CHOICES = [
    (DISCOUNT_NONE, "No discount"),
    (DISCOUNT_PERCENT, "Percent off"),
    (DISCOUNT_AMOUNT, "Flat amount off"),
]

CENTS = Decimal("0.01")


def compute_discount(base, discount_type, discount_value):
    """Money taken off `base` for the given discount. Never below 0, never above base."""
    base = Decimal(base or 0)
    value = Decimal(discount_value or 0)
    if base <= 0 or value <= 0 or discount_type not in (DISCOUNT_PERCENT, DISCOUNT_AMOUNT):
        return Decimal("0.00")
    if discount_type == DISCOUNT_PERCENT:
        value = min(value, Decimal("100"))
        amount = base * value / Decimal("100")
    else:
        amount = value
    return min(base, max(Decimal("0"), amount)).quantize(CENTS)


class Sale(models.Model):
    STATUS_OPEN = "open"
    STATUS_COMPLETED = "completed"
    STATUS_VOID = "void"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_VOID, "Void"),
    ]

    invoice_number = models.CharField(max_length=20, unique=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sales")
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Net of every discount, before tax.",
    )
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Whole-order discount applied at the register, on top of any line discounts.
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_CHOICES, default=DISCOUNT_NONE)
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Percent (0-100) or flat amount, depending on discount_type.",
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Money the order discount actually took off — computed, not entered.",
    )
    discount_reason = models.CharField(max_length=150, blank=True)
    discount_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="discounted_sales",
    )
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="voided_sales",
    )
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number or f"Sale #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{timezone.now():%y%m%d%H%M%S%f}"[:-3]
        super().save(*args, **kwargs)

    def recalculate_totals(self, save=True):
        """Line discounts first, then the order discount, then tax on what's left."""
        items = list(self.items.all())
        net_lines = sum((item.line_total for item in items), start=Decimal("0"))
        order_discount = compute_discount(net_lines, self.discount_type, self.discount_value)
        subtotal = (net_lines - order_discount).quantize(CENTS)
        tax = (subtotal * TAX_RATE).quantize(CENTS)
        total = subtotal + tax
        self.discount_amount = order_discount
        self.subtotal, self.tax, self.total = subtotal, tax, total
        if save:
            self.save(update_fields=["discount_amount", "subtotal", "tax", "total"])
        return total

    def set_discount(self, discount_type, value, reason="", user=None, save=True):
        """Apply (or clear) the whole-order discount and re-run the totals."""
        if discount_type not in (DISCOUNT_PERCENT, DISCOUNT_AMOUNT):
            discount_type, value, reason = DISCOUNT_NONE, Decimal("0"), ""
        self.discount_type = discount_type
        self.discount_value = Decimal(value or 0)
        self.discount_reason = (reason or "").strip()[:150]
        self.discount_by = user if discount_type != DISCOUNT_NONE else None
        if save:
            self.save(update_fields=["discount_type", "discount_value", "discount_reason", "discount_by"])
        return self.recalculate_totals(save=save)

    # -- discount / profit read-outs -------------------------------------

    @property
    def gross_subtotal(self):
        """What the cart would have cost with no discounts at all."""
        return sum((item.gross_total for item in self.items.all()), start=Decimal("0"))

    @property
    def item_discount_total(self):
        return sum((item.discount_amount for item in self.items.all()), start=Decimal("0"))

    @property
    def total_discount(self):
        return self.item_discount_total + self.discount_amount

    @property
    def has_discount(self):
        return self.total_discount > 0

    @property
    def discount_label(self):
        if self.discount_type == DISCOUNT_PERCENT:
            return f"{self.discount_value.normalize():f}% off"
        if self.discount_type == DISCOUNT_AMOUNT:
            return f"${self.discount_value} off"
        return ""

    @property
    def cost_total(self):
        """Cost of goods on this sale, from the cost snapshot taken at ring-up."""
        return sum((item.cost_total for item in self.items.all()), start=Decimal("0"))

    @property
    def gross_profit(self):
        """Net sales (post-discount, pre-tax) minus cost of goods."""
        return self.subtotal - self.cost_total

    @property
    def margin_percent(self):
        if not self.subtotal:
            return None
        return (self.gross_profit / self.subtotal) * 100

    @property
    def is_loss(self):
        return self.gross_profit < 0

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), start=Decimal("0"))

    @property
    def balance_due(self):
        return self.total - self.amount_paid

    @property
    def is_void(self):
        return self.status == self.STATUS_VOID

    @property
    def unit_count(self):
        return sum((item.quantity for item in self.items.all()), start=Decimal("0"))


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items"
    )
    color_formula = models.ForeignKey(
        ColorFormula, on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items"
    )
    description = models.CharField(max_length=200, blank=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Cost per unit, snapshotted when the line was rung up so history stays honest.",
    )
    line_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Charged for this line, after its own discount.",
    )
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_CHOICES, default=DISCOUNT_NONE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.description or (self.product.name if self.product else "Custom Item")

    def save(self, *args, **kwargs):
        if not self.description:
            self.description = self.product.name if self.product else (self.color_formula.name if self.color_formula else "Item")
        gross = (self.quantity * self.unit_price).quantize(CENTS)
        self.discount_amount = compute_discount(gross, self.discount_type, self.discount_value)
        self.line_total = (gross - self.discount_amount).quantize(CENTS)
        super().save(*args, **kwargs)

    @property
    def gross_total(self):
        return (self.quantity * self.unit_price).quantize(CENTS)

    @property
    def cost_total(self):
        return (self.quantity * self.unit_cost).quantize(CENTS)

    @property
    def profit(self):
        return self.line_total - self.cost_total

    @property
    def margin_percent(self):
        if not self.line_total:
            return None
        return (self.profit / self.line_total) * 100

    @property
    def is_loss(self):
        """Sold for less than it cost — only meaningful once a cost is on file."""
        return bool(self.unit_cost) and self.profit < 0

    @property
    def has_discount(self):
        return self.discount_amount > 0

    @property
    def discount_label(self):
        if self.discount_type == DISCOUNT_PERCENT:
            return f"{self.discount_value.normalize():f}% off"
        if self.discount_type == DISCOUNT_AMOUNT:
            return f"${self.discount_value} off"
        return ""


class Payment(models.Model):
    METHOD_CASH = "cash"
    METHOD_CARD = "card"
    METHOD_CREDIT = "credit"
    METHOD_CHOICES = [
        (METHOD_CASH, "Cash"),
        (METHOD_CARD, "Card"),
        (METHOD_CREDIT, "Store Credit"),
    ]

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tendered = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    change_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_method_display()} {self.amount} for {self.sale.invoice_number}"
