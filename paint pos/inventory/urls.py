from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("transfer/", views.transfer_create, name="transfer"),
    path("transfers/", views.transfer_list, name="transfer_list"),
    path("transfers/<int:pk>/<str:decision>/", views.transfer_decide, name="transfer_decide"),
    path("adjust/", views.stock_adjust, name="stock_adjust"),
    path("adjustments/", views.adjustment_list, name="adjustments"),
    path("suppliers/", views.supplier_list, name="suppliers"),
    path("suppliers/<int:pk>/toggle/", views.supplier_toggle, name="supplier_toggle"),
    path("suppliers/<int:pk>/delete/", views.supplier_delete, name="supplier_delete"),
    path("purchase-orders/", views.purchase_order_list, name="purchase_orders"),
    path("purchase-orders/new/", views.purchase_order_create, name="purchase_order_create"),
    path("purchase-orders/<int:pk>/", views.purchase_order_detail, name="purchase_order_detail"),
    path("purchase-orders/<int:pk>/discount/", views.purchase_order_set_discount, name="purchase_order_set_discount"),
    path("purchase-orders/<int:pk>/receipt/", views.purchase_order_receipt, name="purchase_order_receipt"),
    path("purchase-orders/<int:pk>/receive/", views.purchase_order_receive, name="purchase_order_receive"),
    path("purchase-orders/<int:pk>/cancel/", views.purchase_order_cancel, name="purchase_order_cancel"),
    path("warehouses/", views.warehouse_list, name="warehouses"),
]
