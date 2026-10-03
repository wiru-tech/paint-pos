from django.conf import settings
from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_warehouse = models.BooleanField(
        default=False,
        help_text="Central storage location — excluded from retail-only pickers (staff assignment, "
                   "dashboard, reports) but still a valid stock-transfer endpoint.",
    )
    allow_custom_mixes = models.BooleanField(
        default=True,
        help_text="OFF: cashiers can only add colors from the Color Menu catalog at the Tinting Desk — "
                   "manual HEX/RGB/wheel mixing is locked for them (managers are never restricted).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Notification(models.Model):
    """An in-app alert for one staff member (low stock, transfer request, …)."""

    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_CRITICAL = "critical"
    LEVEL_CHOICES = [
        (LEVEL_INFO, "Info"),
        (LEVEL_WARNING, "Warning"),
        (LEVEL_CRITICAL, "Critical"),
    ]

    ICONS = {
        "low_stock": "inventory_2",
        "transfer": "swap_horiz",
        "purchase_order": "local_shipping",
        "sale": "point_of_sale",
    }

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    category = models.CharField(
        max_length=40, blank=True, help_text="Grouping key, e.g. low_stock / transfer"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.title} -> {self.recipient}"

    @property
    def icon(self):
        if self.category in self.ICONS:
            return self.ICONS[self.category]
        return "error" if self.level == self.LEVEL_CRITICAL else "notifications"

    def mark_read(self, save=True):
        self.is_read = True
        if save:
            self.save(update_fields=["is_read"])
        return self
