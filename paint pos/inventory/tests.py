from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from catalog.models import Category, Product
from core.models import Branch
from inventory.models import StockLevel

User = get_user_model()


class InventoryTests(TestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(name="Branch A", code="BRA")
        self.branch_b = Branch.objects.create(name="Branch B", code="BRB")
        self.user = User.objects.create_user(username="mgr", password="pass12345")
        Profile.objects.update_or_create(user=self.user, defaults={"branch": self.branch_a, "role": Profile.ROLE_MANAGER})
        self.category = Category.objects.create(name="Tools & Equipment")
        self.product = Product.objects.create(
            sku="TL-1", name="Test Tool", category=self.category, unit_label="Each", unit_price=Decimal("10.00")
        )
        StockLevel.objects.create(branch=self.branch_a, product=self.product, quantity=20, reorder_threshold=5)
        StockLevel.objects.create(branch=self.branch_b, product=self.product, quantity=2, reorder_threshold=5)

    def test_list_requires_login(self):
        response = self.client.get(reverse("inventory:list"))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_products_and_status(self):
        self.client.login(username="mgr", password="pass12345")
        response = self.client.get(reverse("inventory:list"))
        self.assertContains(response, "TL-1")
        self.assertContains(response, "Low Stock")

    def test_transfer_moves_stock(self):
        self.client.login(username="mgr", password="pass12345")
        self.client.post(reverse("inventory:transfer"), {
            "product_id": self.product.id, "from_branch": self.branch_a.id,
            "to_branch": self.branch_b.id, "quantity": 5,
        })
        a = StockLevel.objects.get(branch=self.branch_a, product=self.product)
        b = StockLevel.objects.get(branch=self.branch_b, product=self.product)
        self.assertEqual(a.quantity, 15)
        self.assertEqual(b.quantity, 7)

    def test_transfer_rejects_insufficient_stock(self):
        self.client.login(username="mgr", password="pass12345")
        self.client.post(reverse("inventory:transfer"), {
            "product_id": self.product.id, "from_branch": self.branch_b.id,
            "to_branch": self.branch_a.id, "quantity": 999,
        })
        b = StockLevel.objects.get(branch=self.branch_b, product=self.product)
        self.assertEqual(b.quantity, 2)
