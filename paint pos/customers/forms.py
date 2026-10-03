from django import forms

from accounts.forms import style

from .models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "customer_type", "phone", "email", "is_pro", "favorite_brand", "store_credit", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["favorite_brand"].required = False
        self.fields["customer_type"].required = False
        self.fields["store_credit"].help_text = "Opening balance — later changes are logged as loyalty entries."
        self.fields["customer_type"].help_text = "Walk-ins are name-only and don't earn loyalty points."
        style(self.fields)

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("A customer name is required.")
        return name

    def clean_customer_type(self):
        return self.cleaned_data.get("customer_type") or Customer.TYPE_REGULAR
