from django import forms

from accounts.forms import style

from .models import Brand, Category, Pigment, Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "sku", "name", "category", "brand", "unit_label", "unit_price", "cost_price",
            "is_tintable", "reorder_threshold", "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].required = False
        self.fields["unit_label"].widget.attrs["placeholder"] = "1 Gal, 4L, Each…"
        self.fields["cost_price"].help_text = "What this unit costs you — drives the Profit & Loss report."
        style(self.fields)

    def clean_sku(self):
        return (self.cleaned_data.get("sku") or "").strip().upper()


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self.fields)


class PigmentForm(forms.ModelForm):
    class Meta:
        model = Pigment
        fields = ("code", "name", "hex_color", "cost_per_ml")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hex_color"].widget.attrs["placeholder"] = "#RRGGBB"
        style(self.fields)

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()

    def clean_hex_color(self):
        value = (self.cleaned_data.get("hex_color") or "").strip().upper()
        if not value.startswith("#"):
            value = f"#{value}"
        if len(value) != 7:
            raise forms.ValidationError("Use a 6-digit hex colour, e.g. #1A2B3C.")
        return value
