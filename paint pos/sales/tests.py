from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from catalog.models import Category, Pigment, Product
from core.models import Branch
from inventory.models import StockLevel
from sales.models import Sale

User = get_user_model()


class SalesDeskTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TST")
        self.user = User.objects.create_user(username="tester", password="pass12345")
        Profile.objects.update_or_create(user=self.user, defaults={"branch": self.branch, "role": Profile.ROLE_CASHIER})
        self.category = Category.objects.create(name="Interior Paint")
        self.product = Product.objects.create(
            sku="TST-001", name="Test Paint", category=self.category,
            unit_label="1 Gal", unit_price=Decimal("50.00"),
        )
        StockLevel.objects.create(branch=self.branch, product=self.product, quantity=10, reorder_threshold=2)

    def test_desk_requires_login(self):
        response = self.client.get(reverse("sales:desk"))
        self.assertEqual(response.status_code, 302)

    def test_full_sale_flow_decrements_stock_and_completes(self):
        self.client.login(username="tester", password="pass12345")
        self.assertEqual(self.client.get(reverse("sales:desk")).status_code, 200)

        add_response = self.client.post(reverse("sales:cart_add"), {"sku": "TST-001"})
        self.assertTrue(add_response.json()["success"])

        sale = Sale.objects.get(cashier=self.user, status=Sale.STATUS_OPEN)
        self.assertEqual(sale.items.count(), 1)
        self.assertEqual(sale.subtotal, Decimal("50.00"))
        self.assertEqual(sale.tax, Decimal("4.00"))
        self.assertEqual(sale.total, Decimal("54.00"))

        pay_response = self.client.post(reverse("sales:add_payment"), {"method": "cash", "tendered": "60.00"})
        data = pay_response.json()
        self.assertTrue(data["completed"])
        self.assertIn(f"/sales/receipt/{sale.pk}/", data["redirect_url"])

        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.STATUS_COMPLETED)

        stock = StockLevel.objects.get(branch=self.branch, product=self.product)
        self.assertEqual(stock.quantity, 9)

        receipt_response = self.client.get(reverse("sales:receipt", args=[sale.pk]))
        self.assertEqual(receipt_response.status_code, 200)

    def test_tint_calculate_and_add_to_cart(self):
        self.product.is_tintable = True
        self.product.save(update_fields=["is_tintable"])
        for code, name, hex_color in [
            ("B", "Lamp Black", "#000000"), ("C", "Yellow Oxide", "#E5D040"),
            ("E", "Phthalo Blue", "#0055A4"), ("KX", "Titanium White", "#FFFFFF"),
            ("TG", "Thalo Green", "#0B6E4F"),
        ]:
            Pigment.objects.create(code=code, name=name, hex_color=hex_color)
        self.client.login(username="tester", password="pass12345")

        calc = self.client.get(reverse("sales:tint_calculate"), {"hex": "2D4A3E", "base_size": "4L"})
        self.assertTrue(calc.json()["success"])

        add = self.client.post(reverse("sales:tint_add"), {
            "hex": "2D4A3E", "base_size": "4L", "product_id": self.product.id, "name": "Test Forest",
        })
        data = add.json()
        self.assertTrue(data["success"], data["error"])

        sale = Sale.objects.get(cashier=self.user, status=Sale.STATUS_OPEN)
        self.assertEqual(sale.items.filter(color_formula__isnull=False).count(), 1)
