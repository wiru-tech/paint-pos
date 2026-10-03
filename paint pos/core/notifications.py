"""Helpers for creating in-app notifications (and optional email copies).

Used by the low-stock checker, the transfer approval workflow and the
purchase-order receiving flow. Email uses whatever ``EMAIL_BACKEND`` is
configured — the console backend in development.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from .models import Notification

User = get_user_model()


def managers_for_branch(branch=None):
    """Managers at ``branch`` (plus every manager if no branch is given)."""
    qs = User.objects.filter(is_active=True, profile__role="manager")
    if branch is not None:
        qs = qs.filter(profile__branch=branch)
    return qs.distinct()


def notify(recipients, title, message="", *, level=Notification.LEVEL_INFO,
           url="", branch=None, category="", email=False, dedupe=False):
    """Create a notification for each recipient. Returns the created objects."""
    recipients = [u for u in recipients if u is not None]
    if not recipients:
        return []

    if dedupe:
        already = set(
            Notification.objects.filter(
                recipient__in=recipients, title=title, category=category, is_read=False
            ).values_list("recipient_id", flat=True)
        )
        recipients = [u for u in recipients if u.pk not in already]
        if not recipients:
            return []

    created = Notification.objects.bulk_create([
        Notification(
            recipient=user, branch=branch, level=level,
            title=title, message=message, url=url, category=category,
        )
        for user in recipients
    ])

    if email:
        addresses = [u.email for u in recipients if u.email]
        if addresses:
            send_mail(
                subject=f"[ChromaPOS] {title}",
                message=message or title,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=addresses,
                fail_silently=True,
            )
    return created


def notify_managers(branch, title, message="", **kwargs):
    """Notify every manager at a branch (falls back to all managers)."""
    recipients = list(managers_for_branch(branch))
    if not recipients:
        recipients = list(managers_for_branch(None))
    return notify(recipients, title, message, branch=branch, **kwargs)


def unread_count(user):
    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(recipient=user, is_read=False).count()
