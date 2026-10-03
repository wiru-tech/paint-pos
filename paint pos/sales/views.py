from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.permissions import is_manager, manager_required
from catalog.models import ColorFormula, ColorFormulaLine, Product
from catalog.tinting import CAPACITY_ML, calculate_formula
from customers.models import Customer
from customers.services import spend_credit

from .models import (
    DISCOUNT_AMOUNT, DISCOUNT_NONE, DISCOUNT_PERCENT, Payment, Sale, SaleItem,
)
from .services import (
    VoidError, estimate_surcharge, finalize_sale, get_open_sale, tint_surcharge,
    tint_unit_cost, void_sale,
)

FINISH_CHOICES = ["", "Matte", "Eggshell", "Satin", "Semi-Gloss", "Gloss"]


def _parse_color(params):
    hex_value = (params.get("hex") or "").strip().lstrip("#")
    if len(hex_value) == 6:
        try:
            return int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16)
        except ValueError:
            pass
    try:
        r = max(0, min(255, int(params.get("r", 255))))
        g = max(0, min(255, int(params.get("g", 255))))
        b = max(0, min(255, int(params.get("b", 255))))
        return r, g, b
    except (TypeError, ValueError):
        return 255, 255, 255


def _build_tinting_context(request):
    params = request.GET if request.method == "GET" else request.POST
    tintable_products = list(Product.objects.filter(is_tintable=True, is_active=True).order_by("name"))

    # A "Mix This Color" link from the Color Menu carries shade_id. Once it
    # resolves, every color field is pinned to that catalog row — client-sent
    # hex/rgb/name/finish are ignored — so a locked branch can't be bypassed
    # by editing the (disabled) form fields and resubmitting.
    shade_id = (params.get("shade_id") or "").strip()
    locked_shade = None
    if shade_id:
        locked_shade = (
            ColorFormula.objects.filter(id=shade_id, is_catalog_shade=True)
            .select_related("base_product").first()
        )

    profile = getattr(request.user, "profile", None)
    branch = profile.branch if profile else None
    mixes_locked = bool(branch and not branch.allow_custom_mixes and not is_manager(request.user))

    product_id = params.get("product_id")
    base_product = None
    if locked_shade:
        base_product = locked_shade.base_product
    elif product_id:
        base_product = next((p for p in tintable_products if str(p.id) == str(product_id)), None)
    if base_product is None and tintable_products:
        base_product = tintable_products[0]

    valid_sizes = {choice[0] for choice in ColorFormula.BASE_SIZE_CHOICES}
    if locked_shade:
        base_size = locked_shade.base_size
    else:
        base_size = params.get("base_size") or ColorFormula.SIZE_4L
        if base_size not in valid_sizes:
            base_size = ColorFormula.SIZE_4L

    if locked_shade:
        r, g, b = locked_shade.r, locked_shade.g, locked_shade.b
        hex_color = locked_shade.hex_color.lstrip("#").upper()
        name = locked_shade.name
        finish = locked_shade.finish
    else:
        r, g, b = _parse_color(params)
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        name = (params.get("name") or "").strip()
        finish = (params.get("finish") or "").strip()

    if base_product and not (mixes_locked and not locked_shade):
        tint_result = calculate_formula(r, g, b, base_size)
    else:
        # Locked with no pre-approved shade picked: no formula to add, by design.
        tint_result = {"lines": [], "total_volume_ml": Decimal("0"), "capacity_ml": Decimal(str(CAPACITY_ML[base_size])), "warning": False}

    capacity = tint_result["capacity_ml"] or Decimal("1")
    fill_percent = min(100, int((tint_result["total_volume_ml"] / capacity) * 100)) if tint_result["lines"] else 0

    estimated_surcharge = None
    estimated_total = None
    if tint_result["lines"] and base_product:
        estimated_surcharge = estimate_surcharge((line["pigment"], line["volume_ml"]) for line in tint_result["lines"])
        estimated_total = base_product.unit_price + estimated_surcharge

    return {
        "tintable_products": tintable_products,
        "base_product": base_product,
        "base_size": base_size,
        "base_size_choices": ColorFormula.BASE_SIZE_CHOICES,
        "r": r, "g": g, "b": b,
        "hex_color": hex_color,
        "name": name,
        "finish": finish,
        "finish_choices": FINISH_CHOICES,
        "tint_result": tint_result,
        "fill_percent": fill_percent,
        "estimated_surcharge": estimated_surcharge,
        "estimated_total": estimated_total,
        "shade_id": locked_shade.id if locked_shade else "",
        "locked_shade": locked_shade,
        "mixes_locked": mixes_locked,
    }


def _cart_context(sale):
    items = list(sale.items.select_related("product", "color_formula").all())
    gross_subtotal = sum((item.gross_total for item in items), start=Decimal("0"))
    item_discount_total = sum((item.discount_amount for item in items), start=Decimal("0"))
    return {
        "sale": sale,
        "items": items,
        "has_items": bool(items),
        "balance_due": sale.balance_due,
        "store_credit": sale.customer.store_credit if sale.customer_id else Decimal("0"),
        "gross_subtotal": gross_subtotal,
        "item_discount_total": item_discount_total,
        "order_discount_total": sale.discount_amount,
        "total_discount": item_discount_total + sale.discount_amount,
    }


def _render_cart_panel(request, sale):
    return render_to_string("sales/_cart_panel.html", _cart_context(sale), request=request)


@login_required
def desk(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.branch:
        return render(request, "sales/no_branch.html", {"active_nav": "sales"})

    sale = get_open_sale(request.user)
    context = {"active_nav": "sales"}
    context.update(_cart_context(sale))
    context.update(_build_tinting_context(request))
    return render(request, "sales/desk.html", context)


@login_required
def product_search(request):
    q = (request.GET.get("q") or "").strip()
    results = []
    if q:
        products = Product.objects.filter(is_active=True).filter(
            Q(sku__icontains=q) | Q(name__icontains=q)
        ).order_by("name")[:8]
        results = [
            {"id": p.id, "sku": p.sku, "name": p.name, "unit_label": p.unit_label, "unit_price": str(p.unit_price)}
            for p in products
        ]
    return JsonResponse({"results": results})


@login_required
@require_POST
def cart_add(request):
    sale = get_open_sale(request.user)
    sku = (request.POST.get("sku") or "").strip()
    error = None
    if not sku:
        error = "Enter a SKU to scan."
    else:
        product = Product.objects.filter(sku__iexact=sku, is_active=True).first()
        if not product:
            error = f'No product found for SKU "{sku}".'
        else:
            item = sale.items.filter(product=product, color_formula__isnull=True).first()
            if item:
                item.quantity += 1
                item.unit_price = product.unit_price
                item.unit_cost = product.cost_price
                item.save()
            else:
                SaleItem.objects.create(
                    sale=sale, product=product, quantity=1,
                    unit_price=product.unit_price, unit_cost=product.cost_price,
                )
            sale.recalculate_totals()
    return JsonResponse({"success": error is None, "error": error, "html": _render_cart_panel(request, sale)})


@login_required
@require_POST
def cart_update_qty(request, item_id):
    sale = get_open_sale(request.user)
    item = sale.items.filter(id=item_id).first()
    error = None
    if not item:
        error = "Item not found."
    else:
        try:
            delta = Decimal(request.POST.get("delta", "0"))
        except Exception:
            delta = Decimal("0")
        new_qty = item.quantity + delta
        if new_qty <= 0:
            item.delete()
        else:
            item.quantity = new_qty
            item.save()
        sale.recalculate_totals()
    return JsonResponse({"success": error is None, "error": error, "html": _render_cart_panel(request, sale)})


@login_required
@require_POST
def cart_remove_item(request, item_id):
    sale = get_open_sale(request.user)
    sale.items.filter(id=item_id).delete()
    sale.recalculate_totals()
    return JsonResponse({"success": True, "error": None, "html": _render_cart_panel(request, sale)})


def _cashier_discount_cap(user):
    """Percent a non-manager may take off without approval. None = no ceiling."""
    if is_manager(user):
        return None
    cap = getattr(settings, "MAX_CASHIER_DISCOUNT_PERCENT", 20)
    return Decimal(str(cap)) if cap is not None else None


def _parse_discount(request, base):
    """Read a discount off the POST body. Returns (type, value, error)."""
    discount_type = (request.POST.get("discount_type") or "").strip()
    if discount_type in ("", DISCOUNT_NONE, "clear"):
        return DISCOUNT_NONE, Decimal("0"), None
    if discount_type not in (DISCOUNT_PERCENT, DISCOUNT_AMOUNT):
        return None, None, "Choose either a percent or a flat amount."

    try:
        value = Decimal(request.POST.get("discount_value") or "0")
    except Exception:
        return None, None, "Enter a number for the discount."
    if value <= 0:
        return None, None, "Enter a discount greater than zero."
    if discount_type == DISCOUNT_PERCENT and value > 100:
        return None, None, "A percent discount can't go above 100%."
    if discount_type == DISCOUNT_AMOUNT and base and value > base:
        return None, None, f"That's more than the ${base} it's being taken off."

    cap = _cashier_discount_cap(request.user)
    if cap is not None:
        as_percent = value if discount_type == DISCOUNT_PERCENT else (
            (value / base * 100) if base else Decimal("0")
        )
        if as_percent > cap:
            return None, None, (
                f"Cashiers can discount up to {cap:.0f}% — this one is "
                f"{as_percent:.1f}%. Ask a manager to approve it."
            )
    return discount_type, value, None


@login_required
@require_POST
def cart_discount(request):
    """Apply, change or clear the whole-order discount on the open sale."""
    sale = get_open_sale(request.user)
    error = None

    if sale.status != Sale.STATUS_OPEN:
        error = "This sale is not open."
    elif not sale.items.exists():
        error = "Add an item before discounting the order."
    else:
        base = sum((item.line_total for item in sale.items.all()), start=Decimal("0"))
        discount_type, value, error = _parse_discount(request, base)
        if error is None:
            sale.set_discount(
                discount_type, value,
                reason=request.POST.get("reason") or "",
                user=request.user,
            )

    return JsonResponse({"success": error is None, "error": error, "html": _render_cart_panel(request, sale)})


@login_required
@require_POST
def item_discount(request, item_id):
    """Apply, change or clear the discount on one cart line."""
    sale = get_open_sale(request.user)
    item = sale.items.filter(id=item_id).first()
    error = None

    if not item:
        error = "Item not found."
    else:
        discount_type, value, error = _parse_discount(request, item.gross_total)
        if error is None:
            item.discount_type = discount_type
            item.discount_value = value
            item.save()
            sale.recalculate_totals()

    return JsonResponse({"success": error is None, "error": error, "html": _render_cart_panel(request, sale)})


@login_required
def tint_calculate(request):
    context = _build_tinting_context(request)
    html = render_to_string("sales/_tinting_panel.html", context, request=request)
    return JsonResponse({"success": True, "html": html})


@login_required
@require_POST
def tint_add(request):
    sale = get_open_sale(request.user)
    context = _build_tinting_context(request)
    base_product = context["base_product"]
    error = None

    if context["mixes_locked"] and not context["locked_shade"]:
        error = "Custom mixes are locked at this branch — pick a color from the Color Menu, or ask a manager to unlock it."
    elif not base_product:
        error = "No tintable product selected."
    elif not context["tint_result"]["lines"]:
        error = "Pick a color first — the current formula has no pigments to mix."
    else:
        r, g, b, base_size, hex_color = context["r"], context["g"], context["b"], context["base_size"], context["hex_color"]
        formula_name = context["name"] or f"Custom Mix #{hex_color}"
        formula = ColorFormula.objects.create(
            name=formula_name,
            hex_color=f"#{hex_color}",
            r=r, g=g, b=b,
            base_product=base_product,
            base_size=base_size,
            finish=context["finish"],
            created_by=request.user,
        )
        ColorFormulaLine.objects.bulk_create([
            ColorFormulaLine(formula=formula, pigment=line["pigment"], shots=line["shots"], volume_ml=line["volume_ml"])
            for line in context["tint_result"]["lines"]
        ])
        surcharge = tint_surcharge(formula)
        SaleItem.objects.create(
            sale=sale,
            product=base_product,
            color_formula=formula,
            description=f"Custom Tint ({formula.name})",
            quantity=1,
            unit_price=base_product.unit_price + surcharge,
            unit_cost=tint_unit_cost(base_product, formula),
        )
        sale.recalculate_totals()

    return JsonResponse({"success": error is None, "error": error, "html": _render_cart_panel(request, sale)})


@login_required
@require_POST
def add_payment(request):
    sale = get_open_sale(request.user)
    method = request.POST.get("method")
    error = None
    completed = False
    change_due = Decimal("0")

    if sale.status != Sale.STATUS_OPEN:
        error = "This sale is not open."
    elif not sale.items.exists():
        error = "Add at least one item before taking payment."
    elif method not in dict(Payment.METHOD_CHOICES):
        error = "Choose a payment method."
    else:
        balance = sale.balance_due
        if balance <= 0:
            error = "This sale is already fully paid."
        elif method == Payment.METHOD_CASH:
            try:
                tendered = Decimal(request.POST.get("tendered") or "0")
            except Exception:
                tendered = Decimal("0")
            if tendered <= 0:
                error = "Enter the amount tendered."
            else:
                amount_applied = min(tendered, balance)
                change_due = max(Decimal("0"), tendered - balance)
                Payment.objects.create(sale=sale, method=method, amount=amount_applied, tendered=tendered, change_due=change_due)
        elif method == Payment.METHOD_CREDIT:
            if not sale.customer_id:
                error = "Attach a customer before paying with store credit."
            else:
                amount_raw = request.POST.get("amount")
                try:
                    amount_applied = Decimal(amount_raw) if amount_raw else balance
                except Exception:
                    amount_applied = balance
                amount_applied = min(amount_applied, balance, sale.customer.store_credit)
                if amount_applied <= 0:
                    error = f"{sale.customer.name} has no store credit available."
                else:
                    try:
                        spend_credit(sale.customer, amount_applied, sale=sale, user=request.user)
                    except ValueError as exc:
                        error = str(exc)
                    else:
                        Payment.objects.create(sale=sale, method=method, amount=amount_applied)
        else:
            amount_raw = request.POST.get("amount")
            try:
                amount_applied = Decimal(amount_raw) if amount_raw else balance
            except Exception:
                amount_applied = balance
            amount_applied = min(amount_applied, balance)
            if amount_applied <= 0:
                error = "Enter a card amount."
            else:
                Payment.objects.create(sale=sale, method=method, amount=amount_applied)

        if error is None and sale.balance_due <= 0:
            finalize_sale(sale, user=request.user)
            completed = True
            change_note = f" Change due: ${change_due}" if change_due else ""
            messages.success(request, f"Sale {sale.invoice_number} completed — total ${sale.total}.{change_note}")

    return JsonResponse({
        "success": error is None,
        "error": error,
        "html": _render_cart_panel(request, sale),
        "completed": completed,
        "change_due": str(change_due),
        "balance_due": str(sale.balance_due),
        "redirect_url": reverse("sales:receipt", args=[sale.pk]) if completed else None,
    })


def _visible_sales(user):
    """Cashiers see their own sales; managers see everything at their branch."""
    qs = Sale.objects.select_related("customer", "branch", "cashier", "voided_by")
    if is_manager(user):
        return qs
    return qs.filter(cashier=user)


@login_required
def receipt(request, pk):
    sale = get_object_or_404(
        _visible_sales(request.user).prefetch_related(
            "items__product", "items__color_formula", "payments"
        ),
        pk=pk,
    )
    return render(request, "sales/receipt.html", {"sale": sale, "active_nav": "sales"})


@login_required
def history(request):
    """Completed and voided sales, newest first."""
    q = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or ""
    sales = _visible_sales(request.user).exclude(status=Sale.STATUS_OPEN)
    if status:
        sales = sales.filter(status=status)
    if q:
        sales = sales.filter(Q(invoice_number__icontains=q) | Q(customer__name__icontains=q))

    page = Paginator(sales.order_by("-created_at"), 20).get_page(request.GET.get("page") or 1)
    return render(request, "sales/history.html", {
        "active_nav": "sales", "page": page, "q": q, "status": status,
        "statuses": [c for c in Sale.STATUS_CHOICES if c[0] != Sale.STATUS_OPEN],
    })


@login_required
@require_POST
def attach_customer(request):
    """Link (or unlink) a customer on the open sale, from the desk itself."""
    sale = get_open_sale(request.user)
    customer_id = request.POST.get("customer_id")

    if not customer_id:
        sale.customer = None
        sale.save(update_fields=["customer"])
    else:
        customer = Customer.objects.filter(id=customer_id).first()
        if not customer:
            return JsonResponse({
                "success": False, "error": "Customer not found.",
                "html": _render_cart_panel(request, sale),
            })
        sale.customer = customer
        sale.save(update_fields=["customer"])

    return JsonResponse({
        "success": True, "error": None, "html": _render_cart_panel(request, sale),
    })


@login_required
@require_POST
def attach_walkin(request):
    """Attach a name-only walk-in to the open sale — no phone, no loyalty account."""
    sale = get_open_sale(request.user)
    name = (request.POST.get("name") or "").strip()

    if not name:
        return JsonResponse({
            "success": False, "error": "Enter a name for the walk-in customer.",
            "html": _render_cart_panel(request, sale),
        })

    # Reuse an existing walk-in with the same name rather than piling up
    # duplicate rows every time "Cash Customer" walks back in.
    customer = Customer.objects.filter(
        name__iexact=name, customer_type=Customer.TYPE_WALKIN
    ).first()
    if customer is None:
        customer = Customer.objects.create(name=name, customer_type=Customer.TYPE_WALKIN)

    sale.customer = customer
    sale.save(update_fields=["customer"])
    return JsonResponse({
        "success": True, "error": None, "html": _render_cart_panel(request, sale),
    })


@login_required
def customer_search(request):
    q = (request.GET.get("q") or "").strip()
    results = []
    if q:
        matches = Customer.objects.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q)
        ).order_by("customer_type", "name")[:8]
        results = [
            {
                "id": c.id, "name": c.name, "phone": c.phone,
                "store_credit": str(c.store_credit), "points": c.loyalty_points,
                "type": c.customer_type, "is_walkin": c.is_walkin,
            }
            for c in matches
        ]
    return JsonResponse({"results": results})


@login_required
@manager_required
@require_POST
def void(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    reason = (request.POST.get("reason") or "").strip()
    try:
        void_sale(sale, user=request.user, reason=reason)
    except VoidError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Voided {sale.invoice_number} — stock restored and loyalty reversed.",
        )
    return redirect(request.POST.get("next") or "sales:history")


@login_required
@require_POST
def email_receipt(request, pk):
    sale = get_object_or_404(_visible_sales(request.user).prefetch_related("items", "payments"), pk=pk)
    address = (request.POST.get("email") or "").strip() or (sale.customer.email if sale.customer_id else "")

    if not address:
        messages.error(request, "No e-mail address on file for this sale — add one and try again.")
        return redirect("sales:receipt", pk=sale.pk)

    body = render_to_string("sales/receipt_email.txt", {"sale": sale})
    send_mail(
        subject=f"Your ChromaPOS receipt {sale.invoice_number}",
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[address],
        fail_silently=True,
    )
    messages.success(request, f"Receipt {sale.invoice_number} e-mailed to {address}.")
    return redirect("sales:receipt", pk=sale.pk)
