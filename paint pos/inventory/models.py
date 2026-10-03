from decimal import Decimal

from django.conf import settings
from django.db import models

from catalog.models import Pigment, Product
from core.models import Branch


class PigmentStockLevel(models.Model):
    """On-hand pigment volume at a branch or warehouse."""

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="pigment_stock_levels")
    pigment = models.ForeignKey(Pigment, on_delete=models.CASCADE, related_name="stock_levels")
    volume_ml = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "pigment")
        ordering = ["branch__name", "pigment__code"]

    def __str__(self):
        return f"{self.pigment.code} @ {self.branch.code}: {self.volume_ml}ml"


class StockLevel(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="stock_levels")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_levels")
    quantity = models.PositiveIntegerField(default=0)
    reorder_threshold = models.PositiveIntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "product")
        ordering = ["product__name", "branch__name"]

    def __str__(self):
        return f"{self.product.sku} @ {self.branch.code}: {self.quantity}"

    @property
    def status(self):
        if self.quantity <= 0:
            return "out"
        if self.quantity <= self.reorder_threshold:
            return "low"
        return "in_stock"


class StockTransfer(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    from_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="transfers_out")
    to_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="transfers_in")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="transfers")
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="requested_transfers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="decided_transfers",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.sku}: {self.from_branch.code} -> {self.to_branch.code} ({self.quantity})"

    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING


class StockAdjustment(models.Model):
    """A manual correction to a branch's stock level, with an audit trail."""

    REASON_COUNT = "count"
    REASON_DAMAGE = "damage"
    REASON_RETURN = "return"
    REASON_OTHER = "other"
    REASON_CHOICES = [
        (REASON_COUNT, "Cycle count"),
        (REASON_DAMAGE, "Damaged / written off"),
        (REASON_RETURN, "Customer return"),
        (REASON_OTHER, "Other"),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="adjustments")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="adjustments")
    previous_quantity = models.PositiveIntegerField(default=0)
    new_quantity = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_COUNT)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_adjustments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.sku} @ {self.branch.code}: {self.previous_quantity} -> {self.new_quantity}"

    @property
    def delta(self):
        return self.new_quantity - self.previous_quantity


class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    contact_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    default_discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="This vendor's standing discount — auto-applied to the subtotal of every new purchase order.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ORDERED = "ordered"
    STATUS_RECEIVED = "received"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ORDERED, "Ordered"),
        (STATUS_RECEIVED, "Received"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    reference = models.CharField(max_length=30, unique=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="purchase_orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.CharField(max_length=255, blank=True)

    # Persisted order-level money breakdown — kept in sync with the lines and
    # the discount inputs by recalculate_totals(), rather than computed fresh
    # on every read, so a PO's numbers stay stable even if the vendor's
    # default discount % changes later.
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Sum of every line (quantity x unit cost), before any discount.",
    )
    standard_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Auto-applied from the vendor's default discount % at the time of the last recalculation.",
    )
    manual_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Extra discount off this specific invoice, entered by hand from the vendor's paperwork.",
    )
    grand_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="subtotal - standard_discount - manual_discount. What you actually owe the vendor.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="purchase_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    ordered_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference or f"PO #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.reference:
            from django.utils import timezone
            self.reference = f"PO-{timezone.now():%y%m%d%H%M%S}"
        super().save(*args, **kwargs)

    def recalculate_totals(self, save=True):
        """Re-derive subtotal/standard_discount/grand_total from the current lines,
        the vendor's default discount %, and whatever manual_discount is on file.
        Call after lines are added or manual_discount is edited.
        """
        cents = Decimal("0.01")
        subtotal = sum((line.line_cost for line in self.lines.all()), start=Decimal("0")).quantize(cents)
        rate = self.supplier.default_discount_percentage or Decimal("0")
        standard_discount = (subtotal * rate / Decimal("100")).quantize(cents)
        manual_discount = max(Decimal("0"), min(self.manual_discount or Decimal("0"), subtotal - standard_discount))
        grand_total = max(Decimal("0"), subtotal - standard_discount - manual_discount)

        self.subtotal = subtotal
        self.standard_discount = standard_discount
        self.manual_discount = manual_discount
        self.grand_total = grand_total
        if save:
            self.save(update_fields=["subtotal", "standard_discount", "manual_discount", "grand_total"])
        return grand_total

    @property
    def is_open(self):
        return self.status in (self.STATUS_DRAFT, self.STATUS_ORDERED)

    @property
    def total_cost(self):
        return sum((line.line_cost for line in self.lines.all()), start=Decimal("0"))

    @property
    def total_discount(self):
        """Every dollar taken off this order — the vendor's standard rate plus whatever was entered by hand."""
        return self.standard_discount + self.manual_discount

    @property
    def total_discount_percent(self):
        if not self.subtotal:
            return None
        return self.total_discount / self.subtotal * 100

    @property
    def units_ordered(self):
        return sum(line.quantity_ordered for line in self.lines.all())

    @property
    def units_received(self):
        return sum(line.quantity_received for line in self.lines.all())

    @property
    def savings_vs_standard(self):
        """Total $ saved (or overpaid, if negative) vs. each product's standard cost."""
        total = Decimal("0")
        for line in self.lines.all():
            if line.reference_cost:
                total += (line.reference_cost - line.unit_cost) * line.quantity_ordered
        return total


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchase_lines")
    quantity_ordered = models.PositiveIntegerField(default=1)
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Discount % the vendor quoted for this line, entered by hand from their invoice/quote.",
    )

    class Meta:
        ordering = ["id"]
        unique_together = ("purchase_order", "product")

    def __str__(self):
        return f"{self.product.sku} x{self.quantity_ordered}"

    @property
    def outstanding(self):
        return max(0, self.quantity_ordered - self.quantity_received)

    @property
    def line_cost(self):
        return self.unit_cost * self.quantity_ordered

    @property
    def auto_discount_percent(self):
        """Discount implied by comparing what we paid to the product's standard cost.

        Positive = paid below standard cost (a discount); negative = paid above it.
        None when the product has no standard cost on file to compare against.
        """
        reference = self.product.cost_price
        if not reference:
            return None
        return (reference - self.unit_cost) / reference * 100

    @property
    def reference_cost(self):
        return self.product.cost_price

    @property
    def allocated_order_discount(self):
        """This line's proportional share of the order's standard + manual discount,
        split by how much of the order's subtotal this line represents. Used to show
        a real discount figure on lines that have no quoted/auto discount of their own.
        """
        order = self.purchase_order
        if not order.subtotal:
            return Decimal("0")
        share = self.line_cost / order.subtotal
        return (order.total_discount * share).quantize(Decimal("0.01"))
