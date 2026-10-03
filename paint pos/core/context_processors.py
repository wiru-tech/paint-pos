"""Globals every ChromaPOS template can rely on."""
from .notifications import unread_count


def chromapos(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"is_manager": False, "current_branch": None, "unread_notifications": 0}

    profile = getattr(user, "profile", None)
    return {
        "is_manager": bool(profile and profile.is_manager),
        "current_branch": profile.branch if profile else None,
        "unread_notifications": unread_count(user),
    }
