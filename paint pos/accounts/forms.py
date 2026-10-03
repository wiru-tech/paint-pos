from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from core.models import Branch

from .models import Profile

User = get_user_model()

INPUT_CLASS = (
    "w-full h-9 px-sm py-0 rounded-lg border border-outline-variant "
    "bg-surface-container-lowest pos-input font-body-md text-[13px]"
)
SELECT_CLASS = (
    "w-full h-9 pl-sm pr-7 py-0 rounded-lg border border-outline-variant "
    "bg-surface-container-lowest pos-input font-body-md text-[13px]"
)


def style(fields):
    for field in fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "w-4 h-4 rounded border-outline-variant text-primary")
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault(
                "class",
                "w-full px-sm py-sm rounded-lg border border-outline-variant "
                "bg-surface-container-lowest pos-input font-body-md text-[13px]",
            )
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", SELECT_CLASS)
        else:
            widget.attrs.setdefault("class", INPUT_CLASS)


class StaffCreateForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, initial=Profile.ROLE_CASHIER)
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True, is_warehouse=False), required=False,
        help_text="A branch is required before this account can use the Sales desk.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile = user.profile  # created by the post_save signal
        profile.role = self.cleaned_data["role"]
        profile.branch = self.cleaned_data["branch"]
        profile.save()
        return user


class StaffEditForm(forms.ModelForm):
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES)
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True, is_warehouse=False), required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = self.instance.profile
        self.fields["role"].initial = profile.role
        self.fields["branch"].initial = profile.branch_id
        style(self.fields)

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile = user.profile
        profile.role = self.cleaned_data["role"]
        profile.branch = self.cleaned_data["branch"]
        profile.save()
        return user


class MyDetailsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)
