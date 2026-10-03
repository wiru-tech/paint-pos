from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MyDetailsForm, StaffCreateForm, StaffEditForm, style
from .permissions import is_manager, manager_required

User = get_user_model()


@login_required
@manager_required
def staff_list(request):
    staff = (
        User.objects.select_related("profile", "profile__branch")
        .order_by("-is_active", "username")
    )
    return render(request, "accounts/staff_list.html", {"active_nav": "settings", "staff": staff})


@login_required
@manager_required
def staff_create(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Created account for {user.username}.")
        return redirect("accounts:staff_list")
    return render(request, "accounts/staff_form.html", {
        "active_nav": "settings", "form": form, "title": "New Staff Account",
    })


@login_required
@manager_required
def staff_edit(request, pk):
    member = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    form = StaffEditForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {member.username}.")
        return redirect("accounts:staff_list")
    return render(request, "accounts/staff_form.html", {
        "active_nav": "settings", "form": form, "title": f"Edit {member.username}",
    })


@login_required
def settings_view(request):
    """Personal details + password, plus a link to staff admin for managers."""
    details_form = MyDetailsForm(instance=request.user)
    password_form = PasswordChangeForm(user=request.user)
    style(password_form.fields)

    if request.method == "POST":
        which = request.POST.get("form")
        if which == "details":
            details_form = MyDetailsForm(request.POST, instance=request.user)
            if details_form.is_valid():
                details_form.save()
                messages.success(request, "Your details were saved.")
                return redirect("accounts:settings")
        elif which == "password":
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            style(password_form.fields)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password updated.")
                return redirect("accounts:settings")
        elif which == "tinting_policy" and is_manager(request.user):
            profile = getattr(request.user, "profile", None)
            branch = profile.branch if profile else None
            if branch:
                branch.allow_custom_mixes = bool(request.POST.get("allow_custom_mixes"))
                branch.save(update_fields=["allow_custom_mixes"])
                state = "allowed" if branch.allow_custom_mixes else "locked to the Color Menu only"
                messages.success(request, f"Custom mixing at {branch.name} is now {state} for cashiers.")
            return redirect("accounts:settings")

    return render(request, "accounts/settings.html", {
        "active_nav": "settings",
        "details_form": details_form,
        "password_form": password_form,
        "is_manager": is_manager(request.user),
        "branch": getattr(getattr(request.user, "profile", None), "branch", None),
    })
