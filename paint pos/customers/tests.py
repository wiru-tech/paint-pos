from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from core.models import Branch
from customers.models import Customer

User = get_user_model()


class CustomerViewTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Branch A", code="BRA")
        self.user = User.objects.create_user(username="staff", password="pass12345")
        Profile.objects.update_or_create(user=self.user, defaults={"branch": self.branch, "role": Profile.ROLE_CASHIER})
        self.customer = Customer.objects.create(name="Test Customer", phone="555-0000")

    def test_list_requires_login(self):
        response = self.client.get(reverse("customers:list"))
        self.assertEqual(response.status_code, 302)

    def test_detail_page_loads(self):
        self.client.login(username="staff", password="pass12345")
        response = self.client.get(reverse("customers:detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Customer")

    def test_update_notes(self):
        self.client.login(username="staff", password="pass12345")
        self.client.post(reverse("customers:update_notes", args=[self.customer.pk]), {"notes": "Likes blue."})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.notes, "Likes blue.")
