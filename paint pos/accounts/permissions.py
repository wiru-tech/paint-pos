"""Role enforcement helpers.

Every staff account has a Profile role of Cashier or Manager. Cashiers can
ring up sales, request transfers and read inventory/customer screens.
Managers additionally approve transfers, adjust stock, receive purchase
orders, edit the catalog, void sales, manage staff and open Reports.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import redirect


def is_manager(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.is_manager)


def manager_required(view_func=None, *, redirect_to="core:home"):
    """Allow managers through; bounce cashiers with an explanatory message.

    AJAX/JSON callers get a 403 JSON body instead of a redirect so the POS
    front-end can surface the reason inline.
    """

    def decorator(func):
        @wraps(func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if is_manager(request.user):
                return func(request, *args, **kwargs)

            wants_json = (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or request.headers.get("accept", "").startswith("application/json")
                or request.META.get("CONTENT_TYPE", "").startswith("application/x-www-form-urlencoded")
                and request.method == "POST"
                and request.headers.get("sec-fetch-mode") == "cors"
            )
            if wants_json:
                return JsonResponse(
                    {"success": False, "error": "Manager approval is required for this action."},
                    status=403,
                )
            messages.error(request, "That action needs a manager account.")
            return redirect(redirect_to)

        return _wrapped

    if view_func is not None:
        return decorator(view_func)
    return decorator
