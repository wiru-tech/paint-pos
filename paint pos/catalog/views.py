from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import manager_required
from sales.models import Sale, SaleItem

from .forms import BrandForm, CategoryForm, PigmentForm, ProductForm
from .models import Brand, Category, ColorFormula, Pigment, Product


@login_required
def color_menu(request):
    """Shade Card Catalog — pre-approved colors any cashier can pick without
    hand-mixing. Distinct from the ad-hoc ColorFormula rows created per-sale
    at checkout: only rows explicitly published with is_catalog_shade=True
    ever show up here."""
    q = (request.GET.get("q") or "").strip()
    brand_id = request.GET.get("brand") or ""
    finish = request.GET.get("finish") or ""
    base_type = request.GET.get("base_type") or ""

    shades = (
        ColorFormula.objects.filter(is_catalog_shade=True)
        .select_related("base_product", "base_product__brand")
        .order_by("shade_category", "name")
    )
    if q:
        shades = shades.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if brand_id:
        shades = shades.filter(base_product__brand_id=brand_id)
    if finish:
        shades = shades.filter(finish=finish)
    if base_type:
        shades = shades.filter(base_product__base_type=base_type)

    grouped = {}
    for shade in shades:
        grouped.setdefault(shade.shade_category, []).append(shade)
    sections = [
        {"key": key, "label": label, "shades": grouped[key]}
        for key, label in ColorFormula.SHADE_CATEGORY_CHOICES
        if grouped.get(key)
    ]
    if grouped.get(""):
        sections.append({"key": "", "label": "Other", "shades": grouped[""]})

    return render(request, "catalog/color_menu.html", {
        "active_nav": "color_menu",
        "sections": sections,
        "shades": shades,
        "q": q,
        "brand_id": brand_id,
        "finish": finish,
        "base_type": base_type,
        "brands": Brand.objects.order_by("name"),
        "finish_choices": ["Matte", "Eggshell", "Satin", "Semi-Gloss", "Gloss"],
        "base_types": (
            Product.objects.filter(is_tintable=True).exclude(base_type="")
            .values_list("base_type", flat=True).distinct().order_by("base_type")
        ),
        "has_filters": bool(q or brand_id or finish or base_type),
    })


@login_required
@manager_required
def product_list(request):
    q = (request.GET.get("q") or "").strip()
    category_id = request.GET.get("category") or ""
    show = request.GET.get("show") or "active"

    products = Product.objects.select_related("category", "brand").annotate(
        network_stock=Sum("stock_levels__quantity")
    )
    if show == "active":
        products = products.filter(is_active=True)
    elif show == "inactive":
        products = products.filter(is_active=False)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if category_id:
        products = products.filter(category_id=category_id)

    # Top sellers, last 30 days, network-wide (this page isn't branch-scoped) —
    # flagged with a badge so staff can see what's moving while browsing the
    # catalog itself, not just on the Reports page.
    TOP_SELLER_WINDOW_DAYS = 30
    TOP_SELLER_COUNT = 10
    since = timezone.localdate() - timedelta(days=TOP_SELLER_WINDOW_DAYS)
    top_seller_ids = set(
        SaleItem.objects.filter(
            sale__status=Sale.STATUS_COMPLETED,
            sale__completed_at__date__gte=since,
            product__isnull=False,
        )
        .values("product_id")
        .annotate(revenue=Sum("line_total"))
        .order_by("-revenue")
        .values_list("product_id", flat=True)[:TOP_SELLER_COUNT]
    )

    top_sellers_only = request.GET.get("top_sellers") == "1"
    if top_sellers_only:
        products = products.filter(id__in=top_seller_ids)

    page = Paginator(products.order_by("name"), 15).get_page(request.GET.get("page") or 1)

    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "catalog/product_list.html", {
        "active_nav": "catalog",
        "page": page,
        "q": q,
        "categories": Category.objects.order_by("name"),
        "category_id": category_id,
        "show": show,
        "qs_without_page": params.urlencode(),
        "top_seller_ids": top_seller_ids,
        "top_seller_window_days": TOP_SELLER_WINDOW_DAYS,
        "top_sellers_only": top_sellers_only,
    })


@login_required
@manager_required
def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"Added {product.name} ({product.sku}).")
        return redirect("catalog:product_list")
    return render(request, "catalog/product_form.html", {
        "active_nav": "catalog", "form": form, "title": "New Product",
    })


@login_required
@manager_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {product.name}.")
        return redirect("catalog:product_list")
    return render(request, "catalog/product_form.html", {
        "active_nav": "catalog", "form": form, "title": f"Edit {product.name}", "product": product,
    })


@login_required
@manager_required
def product_toggle(request, pk):
    """Retire or restore a product without deleting its sales history."""
    if request.method != "POST":
        return redirect("catalog:product_list")
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    messages.success(
        request,
        f"{product.name} is now {'active' if product.is_active else 'retired'}.",
    )
    return redirect(request.POST.get("next") or "catalog:product_list")


@login_required
@manager_required
def reference_data(request):
    """Categories, brands and the pigment set used by the tinting desk."""
    category_form = CategoryForm(prefix="category")
    brand_form = BrandForm(prefix="brand")
    pigment_form = PigmentForm(prefix="pigment")

    if request.method == "POST":
        which = request.POST.get("form")
        if which == "category":
            category_form = CategoryForm(request.POST, prefix="category")
            if category_form.is_valid():
                category_form.save()
                messages.success(request, "Category added.")
                return redirect("catalog:reference_data")
        elif which == "brand":
            brand_form = BrandForm(request.POST, prefix="brand")
            if brand_form.is_valid():
                brand_form.save()
                messages.success(request, "Brand added.")
                return redirect("catalog:reference_data")
        elif which == "pigment":
            pigment_form = PigmentForm(request.POST, prefix="pigment")
            if pigment_form.is_valid():
                pigment_form.save()
                messages.success(request, "Pigment added.")
                return redirect("catalog:reference_data")

    return render(request, "catalog/reference_data.html", {
        "active_nav": "catalog",
        "categories": Category.objects.annotate(product_count=Count("products")).order_by("name"),
        "brands": Brand.objects.annotate(product_count=Count("products")).order_by("name"),
        "pigments": Pigment.objects.order_by("code"),
        "category_form": category_form,
        "brand_form": brand_form,
        "pigment_form": pigment_form,
    })


@login_required
@manager_required
def pigment_edit(request, pk):
    pigment = get_object_or_404(Pigment, pk=pk)
    form = PigmentForm(request.POST or None, instance=pigment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated pigment {pigment.code}.")
        return redirect("catalog:reference_data")
    return render(request, "catalog/product_form.html", {
        "active_nav": "catalog", "form": form, "title": f"Edit Pigment {pigment.code}",
        "cancel_url": "catalog:reference_data",
    })