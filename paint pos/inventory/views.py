from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.permissions import is_manager, manager_required
from catalog.models import Brand, Category, Product
from core.models import Branch

from .forms import ManualDiscountForm, PurchaseOrderForm, SupplierForm
from .models import (
    PigmentStockLevel, PurchaseOrder, PurchaseOrderLine, StockAdjustment, StockLevel,
    StockTransfer, Supplier,
)
from .services import (
    TransferError, adjust_stock, apply_transfer, build_reorder_suggestions,
    receive_purchase_order, reject_transfer, request_transfer,
)


@login_required
def product_list(request):
    branches = list(Branch.objects.filter(is_active=True, is_warehouse=False).order_by("name"))

    selected_codes = request.GET.getlist("branch")
    if not selected_codes:
        selected_codes = [b.code for b in branches]
    selected_branches = [b for b in branches if b.code in selected_codes]

    q = (request.GET.get("q") or "").strip()
    category_id = request.GET.get("category") or ""
    brand_id = request.GET.get("brand") or ""
    status_filter = request.GET.get("status") or ""

    products_qs = Product.objects.filter(is_active=True).select_related("category", "brand").order_by("name")
    if q:
        products_qs = products_qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if category_id:
        products_qs = products_qs.filter(category_id=category_id)
    if brand_id:
        products_qs = products_qs.filter(brand_id=brand_id)

    products = list(products_qs)
    stock_map = {}
    for level in StockLevel.objects.filter(product__in=products).select_related("branch"):
        stock_map.setdefault(level.product_id, {})[level.branch_id] = level

    rows = []
    for product in products:
        product_stock = stock_map.get(product.id, {})
        branch_quantities = [
            {
                "branch": b,
                "quantity": product_stock[b.id].quantity if b.id in product_stock else 0,
                "status": product_stock[b.id].status if b.id in product_stock else "out",
            }
            for b in branches
        ]
        total_network = sum(bq["quantity"] for bq in branch_quantities)

        selected_levels = [product_stock[b.id] for b in selected_branches if b.id in product_stock]
        if not selected_levels:
            status = "out"
        elif any(lvl.status == "out" for lvl in selected_levels):
            status = "out"
        elif any(lvl.status == "low" for lvl in selected_levels):
            status = "low"
        else:
            status = "in_stock"

        rows.append({
            "product": product,
            "branch_quantities": [bq for bq in branch_quantities if bq["branch"] in selected_branches],
            "total_network": total_network,
            "status": status,
        })

    summary = {
        "total": len(rows),
        "in_stock": sum(1 for r in rows if r["status"] == "in_stock"),
        "low": sum(1 for r in rows if r["status"] == "low"),
        "out": sum(1 for r in rows if r["status"] == "out"),
    }

    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]

    paginator = Paginator(rows, 10)
    page = paginator.get_page(request.GET.get("page") or 1)

    base_params = request.GET.copy()
    base_params.pop("page", None)
    branch_links = []
    for b in branches:
        codes = set(selected_codes)
        if b.code in codes:
            codes.discard(b.code)
        else:
            codes.add(b.code)
        params = base_params.copy()
        params.setlist("branch", sorted(codes))
        branch_links.append({"branch": b, "active": b.code in selected_codes, "qs": params.urlencode()})

    qs_without_page = base_params.urlencode()

    status_links = []
    for value, label in [("", "Total Products"), ("in_stock", "In Stock"), ("low", "Low Stock"), ("out", "Out of Stock")]:
        params = base_params.copy()
        params.pop("status", None)
        if value:
            params["status"] = value
        status_links.append({
            "value": value,
            "label": label,
            "count": summary["total"] if not value else summary[value],
            "qs": params.urlencode(),
            "active": status_filter == value,
        })

    context = {
        "active_nav": "inventory",
        "branches": branches,
        # Transfers/adjustments can target a warehouse even though the retail-only
        # "Branches Shown" chips and table columns above stay branch-only.
        "transfer_branches": Branch.objects.filter(is_active=True).order_by("is_warehouse", "name"),
        "selected_branches": selected_branches,
        "branch_links": branch_links,
        "categories": Category.objects.order_by("name"),
        "brands": Brand.objects.order_by("name"),
        "category_id": category_id,
        "brand_id": brand_id,
        "status_filter": status_filter,
        "summary": summary,
        "status_links": status_links,
        "q": q,
        "page": page,
        "qs_without_page": qs_without_page,
        "selected_codes": selected_codes,
        "has_filters": bool(q or category_id or brand_id or status_filter or len(selected_codes) != len(branches)),
    }
    return render(request, "inventory/list.html", context)


@login_required
def transfer_create(request):
    """Managers move stock immediately; cashiers raise a request for approval."""
    if request.method != "POST":
        return redirect("inventory:list")

    product = Product.objects.filter(id=request.POST.get("product_id")).first()
    from_branch = Branch.objects.filter(id=request.POST.get("from_branch")).first()
    to_branch = Branch.objects.filter(id=request.POST.get("to_branch")).first()
    note = (request.POST.get("note") or "").strip()
    try:
        quantity = int(request.POST.get("quantity") or 0)
    except ValueError:
        quantity = 0

    redirect_target = request.POST.get("next") or reverse("inventory:list")

    if not product or not from_branch or not to_branch:
        messages.error(request, "Select a product and both branches for the transfer.")
    elif from_branch == to_branch:
        messages.error(request, "Pick two different branches to transfer stock.")
    elif quantity <= 0:
        messages.error(request, "Enter a quantity greater than zero.")
    elif not is_manager(request.user):
        request_transfer(
            product=product, from_branch=from_branch, to_branch=to_branch,
            quantity=quantity, user=request.user, note=note,
        )
        messages.success(
            request,
            f"Requested {quantity} x {product.name} from {from_branch.name} — "
            f"a manager at {from_branch.name} has to approve it.",
        )
    else:
        transfer = StockTransfer(
            product=product, from_branch=from_branch, to_branch=to_branch,
            quantity=quantity, created_by=request.user, note=note,
            status=StockTransfer.STATUS_PENDING,
        )
        transfer.save()
        try:
            apply_transfer(transfer, user=request.user)
        except TransferError as exc:
            transfer.delete()
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Transferred {quantity} x {product.name} from {from_branch.name} to {to_branch.name}.",
            )

    return redirect(redirect_target)


@login_required
def transfer_list(request):
    """Every transfer, newest first — pending ones can be decided by managers."""
    status = request.GET.get("status") or StockTransfer.STATUS_PENDING
    transfers = StockTransfer.objects.select_related(
        "product", "from_branch", "to_branch", "created_by", "decided_by"
    )
    if status != "all":
        transfers = transfers.filter(status=status)

    return render(request, "inventory/transfers.html", {
        "active_nav": "inventory",
        "transfers": transfers[:100],
        "status": status,
        "status_choices": StockTransfer.STATUS_CHOICES,
        "pending_count": StockTransfer.objects.filter(status=StockTransfer.STATUS_PENDING).count(),
    })


@login_required
@manager_required
@require_POST
def transfer_decide(request, pk, decision):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    note = (request.POST.get("decision_note") or "").strip()

    try:
        if decision == "approve":
            apply_transfer(transfer, user=request.user, note=note)
            messages.success(
                request,
                f"Approved: {transfer.quantity} x {transfer.product.name} moved to {transfer.to_branch.name}.",
            )
        elif decision == "reject":
            reject_transfer(transfer, user=request.user, note=note)
            messages.success(request, f"Rejected transfer of {transfer.product.name}.")
        else:
            messages.error(request, "Choose approve or reject.")
    except TransferError as exc:
        messages.error(request, str(exc))

    return redirect(request.POST.get("next") or "inventory:transfer_list")


@login_required
def adjustment_list(request):
    adjustments = StockAdjustment.objects.select_related(
        "product", "branch", "created_by"
    )[:200]
    return render(request, "inventory/adjustments.html", {
        "active_nav": "inventory", "adjustments": adjustments,
    })


@login_required
@manager_required
@require_POST
def stock_adjust(request):
    """Correct a stock level (cycle count, damage, return) with an audit trail."""
    product = Product.objects.filter(id=request.POST.get("product_id")).first()
    branch = Branch.objects.filter(id=request.POST.get("branch")).first()
    reason = request.POST.get("reason") or StockAdjustment.REASON_COUNT
    note = (request.POST.get("note") or "").strip()
    try:
        new_quantity = int(request.POST.get("new_quantity"))
    except (TypeError, ValueError):
        new_quantity = -1

    if not product or not branch:
        messages.error(request, "Pick a product and a branch to adjust.")
    elif new_quantity < 0:
        messages.error(request, "Enter a counted quantity of zero or more.")
    else:
        adjustment = adjust_stock(
            branch=branch, product=product, new_quantity=new_quantity,
            reason=reason, note=note, user=request.user,
        )
        messages.success(
            request,
            f"{product.name} at {branch.name}: {adjustment.previous_quantity} -> {adjustment.new_quantity}.",
        )
    return redirect(request.POST.get("next") or "inventory:list")


# --------------------------------------------------------------------------
# Suppliers & purchase orders
# --------------------------------------------------------------------------

@login_required
@manager_required
def supplier_list(request):
    editing = Supplier.objects.filter(pk=request.GET.get("edit")).first()

    if request.method == "POST":
        instance = Supplier.objects.filter(pk=request.POST.get("supplier_id")).first()
        form = SupplierForm(request.POST, instance=instance)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f"{'Updated' if instance else 'Added'} supplier {supplier.name}.")
            return redirect("inventory:suppliers")
    else:
        form = SupplierForm(instance=editing)

    rows = []
    for supplier in Supplier.objects.all():
        orders = list(
            PurchaseOrder.objects.filter(supplier=supplier).prefetch_related("lines__product")
        )
        # No payment ledger exists yet against POs, so "outstanding" is the
        # committed cost of everything ordered or received but not cancelled —
        # i.e. what's owed to the vendor regardless of draft-stage POs.
        # Uses grand_total (net of both the vendor's standard discount and any
        # manual discount from their invoice), not the gross subtotal.
        outstanding = sum(
            (o.grand_total for o in orders if o.status in (PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_RECEIVED)),
            start=Decimal("0"),
        )

        # Auto-detected discount: how this vendor's actual prices compare to each
        # product's standard cost on file, weighted by how much was ordered at
        # that standard cost (so a big order on one product isn't drowned out by
        # many small lines on others).
        reference_total = Decimal("0")
        savings_total = Decimal("0")
        quoted_discounts = []
        for order in orders:
            if order.status == PurchaseOrder.STATUS_CANCELLED:
                continue
            for line in order.lines.all():
                if line.reference_cost:
                    reference_total += line.reference_cost * line.quantity_ordered
                    savings_total += (line.reference_cost - line.unit_cost) * line.quantity_ordered
                if line.discount_percent:
                    quoted_discounts.append(line.discount_percent)

        avg_auto_discount = (savings_total / reference_total * 100) if reference_total else None
        avg_quoted_discount = (sum(quoted_discounts) / len(quoted_discounts)) if quoted_discounts else None

        rows.append({
            "supplier": supplier,
            "orders": sorted(orders, key=lambda o: o.created_at, reverse=True),
            "po_count": len(orders),
            "outstanding": outstanding,
            "avg_auto_discount": avg_auto_discount,
            "avg_quoted_discount": avg_quoted_discount,
        })

    all_auto = [r["avg_auto_discount"] for r in rows if r["avg_auto_discount"] is not None]
    stats = {
        "total_suppliers": len(rows),
        "active_suppliers": sum(1 for r in rows if r["supplier"].is_active),
        "total_pos": sum(r["po_count"] for r in rows),
        "total_outstanding": sum((r["outstanding"] for r in rows), start=Decimal("0")),
        "avg_discount": (sum(all_auto) / len(all_auto)) if all_auto else None,
    }

    return render(request, "inventory/suppliers.html", {
        "active_nav": "suppliers",
        "rows": rows,
        "stats": stats,
        "form": form,
        "editing": editing,
    })


@login_required
@manager_required
@require_POST
def supplier_toggle(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.is_active = not supplier.is_active
    supplier.save(update_fields=["is_active"])
    messages.success(request, f"{supplier.name} is now {'active' if supplier.is_active else 'inactive'}.")
    return redirect("inventory:suppliers")


@login_required
@manager_required
@require_POST
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    try:
        supplier.delete()
    except ProtectedError:
        messages.error(
            request,
            f"Can't delete {supplier.name} — they have purchase orders on file. Mark them Inactive instead.",
        )
    else:
        messages.success(request, f"Deleted {supplier.name}.")
    return redirect("inventory:suppliers")


@login_required
@manager_required
def purchase_order_list(request):
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()

    all_orders = PurchaseOrder.objects.select_related("supplier", "branch").prefetch_related("lines__product")

    orders = all_orders
    if status:
        orders = orders.filter(status=status)
    if q:
        orders = orders.filter(Q(reference__icontains=q) | Q(supplier__name__icontains=q))

    paginator = Paginator(orders, 12)
    page = paginator.get_page(request.GET.get("page") or 1)

    stats = {
        "total": all_orders.count(),
        "open": all_orders.filter(status__in=[PurchaseOrder.STATUS_DRAFT, PurchaseOrder.STATUS_ORDERED]).count(),
        "received": all_orders.filter(status=PurchaseOrder.STATUS_RECEIVED).count(),
        "committed_cost": sum(
            (o.grand_total for o in all_orders if o.status in (PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_RECEIVED)),
            start=Decimal("0"),
        ),
    }

    base_params = request.GET.copy()
    base_params.pop("page", None)

    return render(request, "inventory/purchase_orders.html", {
        "active_nav": "inventory",
        "page": page,
        "orders": page.object_list,
        "status": status,
        "q": q,
        "statuses": PurchaseOrder.STATUS_CHOICES,
        "stats": stats,
        "qs_without_page": base_params.urlencode(),
        "has_filters": bool(status or q),
    })


@login_required
@manager_required
def purchase_order_create(request):
    """Start a PO, pre-filled from what the branch needs to reorder."""
    profile = getattr(request.user, "profile", None)
    branch = profile.branch if profile else None
    initial = {"branch": branch}
    if not request.POST and request.GET.get("supplier"):
        initial["supplier"] = request.GET.get("supplier")
    form = PurchaseOrderForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.created_by = request.user
        order.save()

        created_lines = 0
        for key, value in request.POST.items():
            if not key.startswith("qty_"):
                continue
            try:
                quantity = int(value or 0)
            except ValueError:
                continue
            if quantity <= 0:
                continue
            product = Product.objects.filter(id=key[4:]).first()
            if not product:
                continue
            cost_raw = request.POST.get(f"cost_{product.id}") or "0"
            try:
                unit_cost = Decimal(cost_raw)
            except Exception:
                unit_cost = Decimal("0")
            disc_raw = request.POST.get(f"disc_{product.id}") or "0"
            try:
                discount_percent = Decimal(disc_raw)
            except Exception:
                discount_percent = Decimal("0")
            PurchaseOrderLine.objects.create(
                purchase_order=order, product=product,
                quantity_ordered=quantity, unit_cost=unit_cost,
                discount_percent=discount_percent,
            )
            created_lines += 1

        if not created_lines:
            order.delete()
            messages.error(request, "Add at least one line (a quantity greater than zero) to the order.")
        else:
            manual_raw = request.POST.get("manual_discount") or "0"
            try:
                order.manual_discount = Decimal(manual_raw)
            except Exception:
                order.manual_discount = Decimal("0")
            order.recalculate_totals()
            messages.success(request, f"Created {order.reference} with {created_lines} line(s).")
            return redirect("inventory:purchase_order_detail", pk=order.pk)

    # Suggestions follow whichever branch is currently selected in the form.
    suggestion_branch = branch
    posted_branch_id = request.POST.get("branch") or request.GET.get("branch")
    if posted_branch_id:
        suggestion_branch = Branch.objects.filter(id=posted_branch_id).first() or branch

    suggestions = build_reorder_suggestions(suggestion_branch) if suggestion_branch else []
    # Products already offered (with their own qty_<id>/cost_<id> inputs) in the
    # Suggested Reorders table above must not also render in this list — the
    # same product.id in both would collide as duplicate form field names.
    suggested_ids = {row["product"].id for row in suggestions}
    other_products = (
        Product.objects.filter(is_active=True).exclude(id__in=suggested_ids)
        .select_related("category").order_by("category__name", "name")
    )
    other_product_groups = []
    for product in other_products:
        category_name = product.category.name if product.category_id else "Other"
        if not other_product_groups or other_product_groups[-1]["name"] != category_name:
            other_product_groups.append({"name": category_name, "products": []})
        other_product_groups[-1]["products"].append(product)

    return render(request, "inventory/purchase_order_form.html", {
        "active_nav": "inventory",
        "form": form,
        "suggestions": suggestions,
        "branch": suggestion_branch,
        "products": other_products,
        "other_product_groups": other_product_groups,
    })


@login_required
@manager_required
def purchase_order_detail(request, pk):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "branch").prefetch_related("lines__product"),
        pk=pk,
    )
    return render(request, "inventory/purchase_order_detail.html", {
        "active_nav": "inventory", "order": order,
    })


@login_required
@manager_required
def purchase_order_receipt(request, pk):
    """Printable record of what was bought from the vendor — reference, lines, discounts, total."""
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier", "branch", "created_by").prefetch_related("lines__product"),
        pk=pk,
    )
    return render(request, "inventory/purchase_order_receipt.html", {
        "active_nav": "inventory", "order": order,
    })


@login_required
@manager_required
@require_POST
def purchase_order_set_discount(request, pk):
    """Record the extra discount read off the vendor's invoice and re-run the totals."""
    order = get_object_or_404(PurchaseOrder.objects.select_related("supplier"), pk=pk)
    form = ManualDiscountForm(request.POST)
    if form.is_valid():
        order.manual_discount = form.cleaned_data["manual_discount"] or Decimal("0")
        order.recalculate_totals()
        messages.success(request, "Updated the manual discount.")
    else:
        messages.error(request, "Enter a valid discount amount.")
    return redirect("inventory:purchase_order_detail", pk=order.pk)


@login_required
@manager_required
@require_POST
def purchase_order_receive(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.prefetch_related("lines"), pk=pk)
    received = {}
    for line in order.lines.all():
        raw = request.POST.get(f"received_{line.id}")
        try:
            received[line.id] = int(raw or 0)
        except ValueError:
            received[line.id] = 0

    try:
        receive_purchase_order(order, received, user=request.user)
    except TransferError as exc:
        messages.error(request, str(exc))
    else:
        booked = sum(v for v in received.values() if v > 0)
        messages.success(request, f"Booked {booked} unit(s) into {order.branch.name} stock.")
    return redirect("inventory:purchase_order_detail", pk=order.pk)


@login_required
@manager_required
@require_POST
def purchase_order_cancel(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if not order.is_open:
        messages.error(request, "That order is already closed.")
    else:
        order.status = PurchaseOrder.STATUS_CANCELLED
        order.save(update_fields=["status"])
        messages.success(request, f"Cancelled {order.reference}.")
    return redirect("inventory:purchase_orders")


# --------------------------------------------------------------------------
# Warehouses
# --------------------------------------------------------------------------

@login_required
@manager_required
def warehouse_list(request):
    """Central storage locations — kept separate from the retail-branch views above."""
    warehouses = Branch.objects.filter(is_warehouse=True, is_active=True).order_by("name")
    branches = Branch.objects.filter(is_active=True, is_warehouse=False).order_by("name")

    rows = []
    for warehouse in warehouses:
        stock = StockLevel.objects.filter(branch=warehouse)
        totals = stock.aggregate(total=Sum("quantity"))
        base_can_totals = stock.filter(product__is_tintable=True).aggregate(total=Sum("quantity"))
        pigment_totals = PigmentStockLevel.objects.filter(branch=warehouse).aggregate(total=Sum("volume_ml"))
        rows.append({
            "warehouse": warehouse,
            "total_stock": totals["total"] or 0,
            "base_cans": base_can_totals["total"] or 0,
            "pigment_volume_ml": pigment_totals["total"] or Decimal("0"),
        })

    # Pick a branch and see what it currently holds, side by side with the
    # warehouse stock above that could be transferred in to top it up.
    selected_branch = None
    branch_id = request.GET.get("branch")
    if branch_id:
        selected_branch = branches.filter(id=branch_id).first()
    branch_summary = None
    warehouse_stock_rows = []
    warehouse_pigment_rows = []
    if selected_branch:
        branch_stock = StockLevel.objects.filter(branch=selected_branch)
        branch_totals = branch_stock.aggregate(total=Sum("quantity"))
        branch_base_cans = branch_stock.filter(product__is_tintable=True).aggregate(total=Sum("quantity"))
        low_count = sum(1 for lvl in branch_stock if lvl.status in ("low", "out"))
        branch_summary = {
            "total_stock": branch_totals["total"] or 0,
            "base_cans": branch_base_cans["total"] or 0,
            "low_stock_lines": low_count,
        }

        # Every branch draws from the same pool of warehouses — show exactly
        # what's sitting in them, product by product, next to what this
        # branch already has, so a manager can see what's worth pulling in.
        branch_qty_map = {lvl.product_id: lvl.quantity for lvl in branch_stock}
        for level in (
            StockLevel.objects.filter(branch__in=warehouses, quantity__gt=0)
            .select_related("product", "branch").order_by("product__name")
        ):
            warehouse_stock_rows.append({
                "warehouse": level.branch,
                "product": level.product,
                "warehouse_qty": level.quantity,
                "branch_qty": branch_qty_map.get(level.product_id, 0),
            })
        for level in (
            PigmentStockLevel.objects.filter(branch__in=warehouses, volume_ml__gt=0)
            .select_related("pigment", "branch").order_by("pigment__name")
        ):
            warehouse_pigment_rows.append({"warehouse": level.branch, "pigment": level.pigment, "volume_ml": level.volume_ml})

    return render(request, "inventory/warehouses.html", {
        "active_nav": "warehouses",
        "rows": rows,
        "branches": branches,
        "products": Product.objects.filter(is_active=True).order_by("name"),
        "selected_branch": selected_branch,
        "branch_summary": branch_summary,
        "warehouse_stock_rows": warehouse_stock_rows,
        "warehouse_pigment_rows": warehouse_pigment_rows,
    })
