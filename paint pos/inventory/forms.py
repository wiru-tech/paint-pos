from django import forms

from accounts.forms import style
from catalog.models import Product
from core.models import Branch

from .models import PurchaseOrder, StockAdjustment, Supplier


class TransferForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    from_branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True))
    to_branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True))
    quantity = forms.IntegerField(min_value=1)
    note = forms.CharField(max_length=255, required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("from_branch") and cleaned.get("from_branch") == cleaned.get("to_branch"):
            raise forms.ValidationError("Pick two different branches to transfer stock.")
        return cleaned


class StockAdjustmentForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.filter(is_active=True))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True))
    new_quantity = forms.IntegerField(min_value=0)
    reason = forms.ChoiceField(choices=StockAdjustment.REASON_CHOICES)
    note = forms.CharField(max_length=255, required=False)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("name", "contact_name", "email", "phone", "default_discount_percentage", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)


class ManualDiscountForm(forms.Form):
    manual_discount = forms.DecimalField(
        min_value=0, max_digits=10, decimal_places=2, required=False,
        help_text="Extra discount off this invoice, from the vendor's paperwork.",
    )


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("supplier", "branch", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        style(self.fields)
