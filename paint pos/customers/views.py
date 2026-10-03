from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from sales.models import Sale

from .forms import CustomerForm
from .models import Customer
from .services import redeem_block, redeem_credit, redeem_points


@login_required
def customer_list(request):
    q = (request.GET.get("q") or "").strip()
    customer_type = request.GET.get("type") or ""
    customers = Customer.objects.select_related("favorite_brand").order_by("name")
    if q:
        customers = customers.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
    if customer_type in (Customer.TYPE_REGULAR, Customer.TYPE_WALKIN):
        customers = customers.filter(customer_type=customer_type)
    return render(request, "customers/list.html", {
        "active_nav": "customers", "customers": customers, "q": q, "customer_type": customer_type,
        "regular_count": Customer.objects.filter(customer_type=Customer.TYPE_REGULAR).count(),
        "walkin_count": Customer.objects.filter(customer_type=Customer.TYPE_WALKIN).count(),
    })


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer.objects.select_related("favorite_brand"), pk=pk)
    sales = list(
        customer.sales.filter(status=Sale.STATUS_COMPLETED)
        .order_by("-created_at")
        .prefetch_related("items__color_formula", "items__product")[:10]
    )
    total_spend = sum((s.total for s in sales), start=0)
    last_sale = sales[0] if sales else None
    saved_formulas = list(
        customer.saved_formulas.select_related("color_formula", "color_formula__base_product").order_by("-created_at")
    )
    loyalty_entries = list(customer.loyalty_entries.select_related("sale")[:12])

    recent_items = []
    for sale in sales:
        for item in sale.items.all():
            recent_items.append({"sale": sale, "item": item})
    recent_items = recent_items[:10]

    context = {
        "active_nav": "customers",
        "customer": customer,
        "total_spend": total_spend,
        "last_sale": last_sale,
        "saved_formulas": saved_formulas,
        "recent_items": recent_items,
        "loyalty_entries": loyalty_entries,
        "redeem_block": redeem_block(),
        "redeem_credit": redeem_credit(),
        "can_redeem": customer.loyalty_points >= redeem_block(),
    }
    return render(request, "customers/detail.html", context)


@login_required
def update_notes(request, pk):
    if request.method != "POST":
        return redirect("customers:detail", pk=pk)
    customer = get_object_or_404(Customer, pk=pk)
    customer.notes = request.POST.get("notes", "")
    customer.save(update_fields=["notes"])
    messages.success(request, "Notes updated.")
    return redirect("customers:detail", pk=pk)


@login_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        messages.success(request, f"Added {customer.name}.")
        return redirect("customers:detail", pk=customer.pk)
    return render(request, "customers/form.html", {
        "active_nav": "customers", "form": form, "title": "New Customer",
    })


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {customer.name}.")
        return redirect("customers:detail", pk=customer.pk)
    return render(request, "customers/form.html", {
        "active_nav": "customers", "form": form, "title": f"Edit {customer.name}",
        "customer": customer,
    })


@login_required
@require_POST
def redeem(request, pk):
    """Turn loyalty points into store credit."""
    customer = get_object_or_404(Customer, pk=pk)
    try:
        blocks = int(request.POST.get("blocks") or 1)
    except ValueError:
        blocks = 1
    try:
        credit = redeem_points(customer, blocks=blocks, user=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Redeemed points for ${credit} of store credit.")
    return redirect("customers:detail", pk=customer.pk)
