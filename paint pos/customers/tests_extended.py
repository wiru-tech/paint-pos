from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from core.models import Branch

from .models import Customer, LoyaltyEntry

User = get_user_model()


class CustomerCrudTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Cust Branch", code="CST")
        self.user = User.objects.create_user(username="custstaff", password="pass12345")
        Profile.objects.update_or_create(
            user=self.user, defaults={"branch": self.branch, "role": Profile.ROLE_CASHIER}
        )

    def test_create_customer(self):
        self.client.login(username="custstaff", password="pass12345")
        response = self.client.post(reverse("customers:create"), {
            "name": "New Customer", "phone": "555-9999", "email": "",
            "store_credit": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(name="New Customer").exists())

    def test_create_customer_requires_name(self):
        self.client.login(username="custstaff", password="pass12345")
        response = self.client.post(reverse("customers:create"), {
            "name": "", "phone": "", "store_credit": "0",
        })
        self.assertEqual(response.status_code, 200)  # re-renders with errors
        self.assertFalse(Customer.objects.filter(phone="").exists())

    def test_edit_customer(self):
        customer = Customer.objects.create(name="Old Name", phone="111")
        self.client.login(username="custstaff", password="pass12345")
        response = self.client.post(reverse("customers:edit", args=[customer.pk]), {
            "name": "Updated Name", "phone": "222", "store_credit": "0",
        })
        self.assertEqual(response.status_code, 302)
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Updated Name")


class LoyaltyRedeemTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Loyalty Branch", code="LOY")
        self.user = User.objects.create_user(username="loyalstaff", password="pass12345")
        Profile.objects.update_or_create(
            user=self.user, defaults={"branch": self.branch, "role": Profile.ROLE_CASHIER}
        )
        self.customer = Customer.objects.create(name="Points Customer", loyalty_points=250)

    def test_redeem_converts_points_to_credit(self):
        self.client.login(username="loyalstaff", password="pass12345")
        response = self.client.post(reverse("customers:redeem", args=[self.customer.pk]), {"blocks": "2"})
        self.assertEqual(response.status_code, 302)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.loyalty_points, 50)  # 250 - 2*100
        self.assertEqual(self.customer.store_credit, 10)    # 2 * 5.00
        self.assertTrue(LoyaltyEntry.objects.filter(customer=self.customer, kind=LoyaltyEntry.KIND_REDEEM).exists())

    def test_redeem_more_than_available_fails_gracefully(self):
        self.client.login(username="loyalstaff", password="pass12345")
        response = self.client.post(reverse("customers:redeem", args=[self.customer.pk]), {"blocks": "50"})
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.loyalty_points, 250)  # unchanged
