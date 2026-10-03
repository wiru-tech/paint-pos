from django.conf import settings
from django.db import models

from catalog.models import Brand, ColorFormula


class Customer(models.Model):
    TYPE_REGULAR = "regular"
    TYPE_WALKIN = "walkin"
    TYPE_CHOICES = [
        (TYPE_REGULAR, "Regular customer"),
        (TYPE_WALKIN, "Walk-in"),
    ]

    name = models.CharField(max_length=150)
    customer_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_REGULAR,
        help_text="Walk-ins are name-only: no phone, loyalty or store credit.",
    )
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_pro = models.BooleanField(default=False)
    store_credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    loyalty_points = models.PositiveIntegerField(default=0)
    favorite_brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="fans"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def initials(self):
        parts = self.name.split()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def is_walkin(self):
        return self.customer_type == self.TYPE_WALKIN

    @property
    def is_regular(self):
        return self.customer_type == self.TYPE_REGULAR


class SavedFormula(models.Model):
    FINISH_MATTE = "matte"
    FINISH_EGGSHELL = "eggshell"
    FINISH_SATIN = "satin"
    FINISH_SEMI_GLOSS = "semi_gloss"
    FINISH_GLOSS = "gloss"
    FINISH_CHOICES = [
        (FINISH_MATTE, "Matte"),
        (FINISH_EGGSHELL, "Eggshell"),
        (FINISH_SATIN, "Satin"),
        (FINISH_SEMI_GLOSS, "Semi-Gloss"),
        (FINISH_GLOSS, "Gloss"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="saved_formulas")
    color_formula = models.ForeignKey(ColorFormula, on_delete=models.CASCADE, related_name="saved_by")
    reference_code = models.CharField(max_length=30, unique=True)
    finish = models.CharField(max_length=20, choices=FINISH_CHOICES, default=FINISH_MATTE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.name}: {self.color_formula.name} ({self.reference_code})"


class LoyaltyEntry(models.Model):
    """One movement of loyalty points or store credit for a customer."""

    KIND_EARN = "earn"
    KIND_REDEEM = "redeem"
    KIND_SPEND = "spend"
    KIND_ADJUST = "adjust"
    KIND_REVERSAL = "reversal"
    KIND_CHOICES = [
        (KIND_EARN, "Points earned"),
        (KIND_REDEEM, "Points redeemed for credit"),
        (KIND_SPEND, "Store credit spent"),
        (KIND_ADJUST, "Manual adjustment"),
        (KIND_REVERSAL, "Reversed (sale voided)"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="loyalty_entries")
    sale = models.ForeignKey(
        "sales.Sale", on_delete=models.SET_NULL, null=True, blank=True, related_name="loyalty_entries"
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    points = models.IntegerField(default=0, help_text="Positive = earned, negative = spent")
    credit_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="loyalty_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "loyalty entries"

    def __str__(self):
        return f"{self.customer.name}: {self.get_kind_display()} ({self.points} pts)"
