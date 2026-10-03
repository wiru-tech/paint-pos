from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.desk, name="desk"),
    path("history/", views.history, name="history"),
    path("products/search/", views.product_search, name="product_search"),
    path("customers/search/", views.customer_search, name="customer_search"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/customer/", views.attach_customer, name="attach_customer"),
    path("cart/customer/walkin/", views.attach_walkin, name="attach_walkin"),
    path("cart/discount/", views.cart_discount, name="cart_discount"),
    path("cart/items/<int:item_id>/qty/", views.cart_update_qty, name="cart_update_qty"),
    path("cart/items/<int:item_id>/discount/", views.item_discount, name="item_discount"),
    path("cart/items/<int:item_id>/remove/", views.cart_remove_item, name="cart_remove_item"),
    path("tint/calculate/", views.tint_calculate, name="tint_calculate"),
    path("tint/add/", views.tint_add, name="tint_add"),
    path("payment/add/", views.add_payment, name="add_payment"),
    path("receipt/<int:pk>/", views.receipt, name="receipt"),
    path("receipt/<int:pk>/email/", views.email_receipt, name="email_receipt"),
    path("<int:pk>/void/", views.void, name="void"),
]
