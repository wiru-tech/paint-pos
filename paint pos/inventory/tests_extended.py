from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from catalog.models import Category, Product
from core.models import Branch

from .models import PurchaseOrder, PurchaseOrderLine, StockAdjustment, StockLevel, Supplier

User = get_user_model()


class PurchaseOrderTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="PO Branch", code="POB")
        self.manager = User.objects.create_user(username="pomgr", password="pass12345")
        Profile.objects.update_or_create(
            user=self.manager, defaults={"branch": self.branch, "role": Profile.ROLE_MANAGER}
        )
        self.category = Category.objects.create(name="PO Category")
        self.product = Product.objects.create(
            sku="PO-1", name="PO Product", category=self.category, unit_label="Each",
            unit_price=Decimal("20.00"), reorder_threshold=5,
        )
        StockLevel.objects.create(branch=self.branch, product=self.product, quantity=2, reorder_threshold=5)
        self.supplier = Supplier.objects.create(name="Acme Coatings")

    def test_create_purchase_order_with_lines(self):
        self.client.login(username="pomgr", password="pass12345")
        response = self.client.post(reverse("inventory:purchase_order_create"), {
            "supplier": self.supplier.id, "branch": self.branch.id, "notes": "restock",
            f"qty_{self.product.id}": "10", f"cost_{self.product.id}": "15.00",
        })
        self.assertEqual(response.status_code, 302)
        order = PurchaseOrder.objects.get(supplier=self.supplier)
        self.assertEqual(order.lines.count(), 1)
        line = order.lines.first()
        self.assertEqual(line.quantity_ordered, 10)
        self.assertEqual(line.unit_cost, Decimal("15.00"))

    def test_receiving_order_books_stock_and_marks_received(self):
        order = PurchaseOrder.objects.create(supplier=self.supplier, branch=self.branch)
        line = PurchaseOrderLine.objects.create(
            purchase_order=order, product=self.product, quantity_ordered=10, unit_cost=Decimal("15.00")
        )
        self.client.login(username="pomgr", password="pass12345")
        response = self.client.post(
            reverse("inventory:purchase_order_receive", args=[order.pk]),
            {f"received_{line.id}": "10"},
        )
        self.assertEqual(response.status_code, 302)

        order.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_RECEIVED)
        self.assertEqual(line.quantity_received, 10)

        level = StockLevel.objects.get(branch=self.branch, product=self.product)
        self.assertEqual(level.quantity, 12)

    def test_partial_receive_leaves_order_ordered(self):
        order = PurchaseOrder.objects.create(supplier=self.supplier, branch=self.branch)
        line = PurchaseOrderLine.objects.create(
            purchase_order=order, product=self.product, quantity_ordered=10, unit_cost=Decimal("15.00")
        )
        self.client.login(username="pomgr", password="pass12345")
        self.client.post(
            reverse("inventory:purchase_order_receive", args=[order.pk]),
            {f"received_{line.id}": "4"},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_ORDERED)


class StockAdjustmentTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Adj Branch", code="ADJ")
        self.manager = User.objects.create_user(username="adjmgr", password="pass12345")
        Profile.objects.update_or_create(
            user=self.manager, defaults={"branch": self.branch, "role": Profile.ROLE_MANAGER}
        )
        self.category = Category.objects.create(name="Adj Category")
        self.product = Product.objects.create(
            sku="ADJ-1", name="Adj Product", category=self.category, unit_label="Each",
            unit_price=Decimal("5.00"),
        )
        StockLevel.objects.create(branch=self.branch, product=self.product, quantity=20, reorder_threshold=5)

    def test_adjustment_updates_stock_and_logs_entry(self):
        self.client.login(username="adjmgr", password="pass12345")
        response = self.client.post(reverse("inventory:stock_adjust"), {
            "product_id": self.product.id, "branch": self.branch.id,
            "new_quantity": "13", "reason": StockAdjustment.REASON_DAMAGE, "note": "water damage",
        })
        self.assertEqual(response.status_code, 302)

        level = StockLevel.objects.get(branch=self.branch, product=self.product)
        self.assertEqual(level.quantity, 13)

        adjustment = StockAdjustment.objects.get(product=self.product)
        self.assertEqual(adjustment.previous_quantity, 20)
        self.assertEqual(adjustment.new_quantity, 13)
        self.assertEqual(adjustment.delta, -7)
