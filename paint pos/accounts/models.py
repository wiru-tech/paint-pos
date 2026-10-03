from django.conf import settings
from django.db import models

from core.models import Branch


class Profile(models.Model):
    ROLE_CASHIER = "cashier"
    ROLE_MANAGER = "manager"
    ROLE_CHOICES = [
        (ROLE_CASHIER, "Cashier"),
        (ROLE_MANAGER, "Manager"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER or self.user.is_superuser
