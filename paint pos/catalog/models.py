from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    unit_label = models.CharField(max_length=30, help_text="e.g. 1 Gal, 4L, 9\" Roller")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="What one unit costs you. Drives profit / loss reporting — leave 0 if unknown.",
    )
    is_tintable = models.BooleanField(default=False, help_text="Can be sent through the Tinting Desk")
    base_type = models.CharField(
        max_length=40, blank=True,
        help_text="Tint-capacity class of this can, e.g. Pastel Base, Deep Base, Neutral Base",
    )
    reorder_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def unit_margin(self):
        """Money made on one unit at list price."""
        return self.unit_price - self.cost_price

    @property
    def margin_percent(self):
        if not self.unit_price:
            return None
        return (self.unit_margin / self.unit_price) * 100

    @property
    def sells_below_cost(self):
        """List price is under cost — every sale at list loses money."""
        return bool(self.cost_price) and self.unit_price < self.cost_price


class Pigment(models.Model):
    code = models.CharField(max_length=10, unique=True, help_text="Colorant code, e.g. B, C, E, KX")
    name = models.CharField(max_length=100)
    hex_color = models.CharField(max_length=7, help_text="#RRGGBB")
    cost_per_ml = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class ColorFormula(models.Model):
    SIZE_1L = "1L"
    SIZE_4L = "4L"
    SIZE_20L = "20L"
    BASE_SIZE_CHOICES = [
        (SIZE_1L, "1L Base"),
        (SIZE_4L, "4L Base"),
        (SIZE_20L, "20L Drum"),
    ]

    CATEGORY_PASTELS = "pastels"
    CATEGORY_NEUTRALS = "neutrals"
    CATEGORY_EARTH_TONES = "earth_tones"
    CATEGORY_BOLD_ACCENTS = "bold_accents"
    CATEGORY_EXTERIOR_SHADES = "exterior_shades"
    SHADE_CATEGORY_CHOICES = [
        (CATEGORY_PASTELS, "Pastels"),
        (CATEGORY_NEUTRALS, "Neutrals"),
        (CATEGORY_EARTH_TONES, "Earth Tones"),
        (CATEGORY_BOLD_ACCENTS, "Bold Accents"),
        (CATEGORY_EXTERIOR_SHADES, "Exterior Shades"),
    ]

    name = models.CharField(max_length=150)
    hex_color = models.CharField(max_length=7, help_text="#RRGGBB")
    r = models.PositiveSmallIntegerField(default=0)
    g = models.PositiveSmallIntegerField(default=0)
    b = models.PositiveSmallIntegerField(default=0)
    base_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="color_formulas")
    base_size = models.CharField(max_length=5, choices=BASE_SIZE_CHOICES, default=SIZE_4L)
    finish = models.CharField(max_length=30, blank=True, help_text="e.g. Matte, Eggshell, Satin")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="color_formulas"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Shade-card catalog fields. Most ColorFormula rows are one-off mixes
    # created at checkout (see sales.views.tint_add) and are NOT catalog
    # shades — only rows explicitly published here show on the Color Menu.
    code = models.CharField(max_length=30, blank=True, help_text="e.g. SW-7005, RAL 9010")
    shade_category = models.CharField(max_length=20, choices=SHADE_CATEGORY_CHOICES, blank=True)
    is_catalog_shade = models.BooleanField(
        default=False, help_text="Show on the Color Menu as a pre-approved, pickable shade"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.hex_color})"

    @property
    def total_volume_ml(self):
        return sum((line.volume_ml for line in self.lines.all()), start=0)


class ColorFormulaLine(models.Model):
    formula = models.ForeignKey(ColorFormula, on_delete=models.CASCADE, related_name="lines")
    pigment = models.ForeignKey(Pigment, on_delete=models.PROTECT, related_name="formula_lines")
    shots = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    volume_ml = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    class Meta:
        ordering = ["pigment__code"]

    def __str__(self):
        return f"{self.formula.name}: {self.pigment.code} {self.shots} shots"
