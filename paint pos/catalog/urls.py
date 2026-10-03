from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("new/", views.product_create, name="product_create"),
    path("<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("<int:pk>/toggle/", views.product_toggle, name="product_toggle"),
    path("color-menu/", views.color_menu, name="color_menu"),
    path("reference/", views.reference_data, name="reference_data"),
    path("pigments/<int:pk>/edit/", views.pigment_edit, name="pigment_edit"),
]
