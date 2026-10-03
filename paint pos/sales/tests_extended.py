from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from catalog.models import Category, Product
from core.models import Branch
from customers.models import Customer, LoyaltyEntry
from inventory.models import StockLevel
from sales.models import Payment, Sale

User = get_user_model()


class SaleLifecycleTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TST2")
        self.cashier = User.objects.create_user(username="cash2", password="pass12345")
        Profile.objects.update_or_create(
            user=self.cashier, defaults={"branch": self.branch, "role": Profile.ROLE_CASHIER}
        )
        self.manager = User.objects.create_user(username="mgr2", password="pass12345")
        Profile.objects.update_or_create(
            user=self.manager, defaults={"branch": self.branch, "role": Profile.ROLE_MANAGER}
        )
        self.category = Category.objects.create(name="Interior Paint 2")
        self.product = Product.objects.create(
            sku="TST-002", name="Test Paint 2", category=self.category,
            unit_label="1 Gal", unit_price=Decimal("50.00"),
        )
        StockLevel.objects.create(branch=self.branch, product=self.product, quantity=10, reorder_threshold=2)
        self.customer = Customer.objects.create(name="Loyal Larry", phone="555-1111")

    def _complete_sale(self, user, attach_customer=True):
        self.client.login(username=user.username, password="pass12345")
        self.client.get(reverse("sales:desk"))
        if attach_customer:
            self.client.post(reverse("sales:attach_customer"), {"customer_id": self.customer.id})
        self.client.post(reverse("sales:cart_add"), {"sku": "TST-002"})
        pay = self.client.post(reverse("sales:add_payment"), {"method": "cash", "tendered": "60.00"})
        return Sale.objects.get(cashier=user, status=Sale.STATUS_COMPLETED)

    def test_completing_sale_with_customer_awards_loyalty(self):
        sale = self._complete_sale(self.cashier)
        self.customer.refresh_from_db()
        self.assertEqual(sale.customer_id, self.customer.id)
        self.assertGreater(self.customer.loyalty_points, 0)
        self.assertTrue(LoyaltyEntry.objects.filter(sale=sale, kind=LoyaltyEntry.KIND_EARN).exists())

    def test_manager_can_void_sale_and_reverse_loyalty_and_stock(self):
        sale = self._complete_sale(self.cashier)
        stock_after_sale = StockLevel.objects.get(branch=self.branch, product=self.product).quantity
        self.customer.refresh_from_db()
        points_after_sale = self.customer.loyalty_points

        self.client.login(username=self.manager.username, password="pass12345")
        response = self.client.post(reverse("sales:void", args=[sale.pk]), {"reason": "customer changed mind"})
        self.assertEqual(response.status_code, 302)

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_VOID)
        self.assertEqual(sale.void_reason, "customer changed mind")
        self.assertIsNotNone(sale.voided_at)

        stock_after_void = StockLevel.objects.get(branch=self.branch, product=self.product).quantity
        self.assertEqual(stock_after_void, stock_after_sale + 1)

        self.customer.refresh_from_db()
        self.assertLess(self.customer.loyalty_points, points_after_sale)
        self.assertTrue(LoyaltyEntry.objects.filter(sale=sale, kind=LoyaltyEntry.KIND_REVERSAL).exists())

    def test_cashier_cannot_void_sale(self):
        sale = self._complete_sale(self.cashier)
        self.client.login(username=self.cashier.username, password="pass12345")
        response = self.client.post(reverse("sales:void", args=[sale.pk]), {"reason": "nope"})
        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_COMPLETED)

    def test_store_credit_payment_deducts_customer_balance(self):
        self.customer.store_credit = Decimal("100.00")
        self.customer.save(update_fields=["store_credit"])

        self.client.login(username=self.cashier.username, password="pass12345")
        self.client.get(reverse("sales:desk"))
        self.client.post(reverse("sales:attach_customer"), {"customer_id": self.customer.id})
        self.client.post(reverse("sales:cart_add"), {"sku": "TST-002"})

        response = self.client.post(reverse("sales:add_payment"), {"method": "credit"})
        data = response.json()
        self.assertTrue(data["success"], data.get("error"))
        self.assertTrue(data["completed"])

        self.customer.refresh_from_db()
        # Sale total is 54.00 (50 + 8% tax); all of it should come from credit.
        self.assertEqual(self.customer.store_credit, Decimal("46.00"))

    def test_sales_history_lists_completed_and_voided(self):
        sale = self._complete_sale(self.cashier, attach_customer=False)
        self.client.login(username=self.manager.username, password="pass12345")
        response = self.client.get(reverse("sales:history"))
        self.assertContains(response, sale.invoice_number)


class RoleGatingTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Gate Branch", code="GTE")
        self.cashier = User.objects.create_user(username="gatecash", password="pass12345")
        Profile.objects.update_or_create(
            user=self.cashier, defaults={"branch": self.branch, "role": Profile.ROLE_CASHIER}
        )
        self.manager = User.objects.create_user(username="gatemgr", password="pass12345")
        Profile.objects.update_or_create(
            user=self.manager, defaults={"branch": self.branch, "role": Profile.ROLE_MANAGER}
        )

    def test_cashier_blocked_from_reports(self):
        self.client.login(username="gatecash", password="pass12345")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 302)

    def test_manager_can_view_reports(self):
        self.client.login(username="gatemgr", password="pass12345")
        response = self.client.get(reverse("core:reports"))
        self.assertEqual(response.status_code, 200)

    def test_cashier_blocked_from_catalog(self):
        self.client.login(username="gatecash", password="pass12345")
        response = self.client.get(reverse("catalog:product_list"))
        self.assertEqual(response.status_code, 302)

    def test_cashier_blocked_from_staff_admin(self):
        self.client.login(username="gatecash", password="pass12345")
        response = self.client.get(reverse("accounts:staff_list"))
        self.assertEqual(response.status_code, 302)


class TransferApprovalTests(TestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(name="Approval A", code="APA")
        self.branch_b = Branch.objects.create(name="Approval B", code="APB")
        self.cashier = User.objects.create_user(username="apcash", password="pass12345")
        Profile.objects.update_or_create(
            user=self.cashier, defaults={"branch": self.branch_a, "role": Profile.ROLE_CASHIER}
        )
        self.manager = User.objects.create_user(username="apmgr", password="pass12345")
        Profile.objects.update_or_create(
            user=self.manager, defaults={"branch": self.branch_a, "role": Profile.ROLE_MANAGER}
        )
        self.category = Category.objects.create(name="Approval Tools")
        self.product = Product.objects.create(
            sku="AP-1", name="Approval Tool", category=self.category, unit_label="Each",
            unit_price=Decimal("10.00"),
        )
        StockLevel.objects.create(branch=self.branch_a, product=self.product, quantity=20, reorder_threshold=5)

    def test_cashier_transfer_creates_pending_request_not_immediate_move(self):
        from inventory.models import StockTransfer

        self.client.login(username="apcash", password="pass12345")
        self.client.post(reverse("inventory:transfer"), {
            "product_id": self.product.id, "from_branch": self.branch_a.id,
            "to_branch": self.branch_b.id, "quantity": 5,
        })
        transfer = StockTransfer.objects.get(product=self.product)
        self.assertEqual(transfer.status, StockTransfer.STATUS_PENDING)
        # Stock should not have moved yet.
        level_a = StockLevel.objects.get(branch=self.branch_a, product=self.product)
        self.assertEqual(level_a.quantity, 20)

    def test_manager_approval_moves_stock(self):
        from inventory.models import StockTransfer
        from inventory.services import request_transfer

        transfer = request_transfer(
            product=self.product, from_branch=self.branch_a, to_branch=self.branch_b,
            quantity=5, user=self.cashier,
        )
        self.client.login(username="apmgr", password="pass12345")
        response = self.client.post(
            reverse("inventory:transfer_decide", args=[transfer.pk, "approve"])
        )
        self.assertEqual(response.status_code, 302)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, StockTransfer.STATUS_COMPLETED)
        level_a = StockLevel.objects.get(branch=self.branch_a, product=self.product)
        level_b = StockLevel.objects.get(branch=self.branch_b, product=self.product)
        self.assertEqual(level_a.quantity, 15)
        self.assertEqual(level_b.quantity, 5)
