from django.urls import path
from . import views

urlpatterns = [
    path("", views.inventory_home, name="inventory_home"),
    path("vat-tu/them/", views.item_form, name="inventory_item_add"),
    path("vat-tu/<int:pk>/", views.item_form, name="inventory_item_edit"),
    path("vat-tu/<int:pk>/xoa/", views.item_delete, name="inventory_item_delete"),
    path("ncc/", views.supplier_form, name="inventory_supplier_add"),
    path("nhap/", views.receive_goods, name="inventory_receive"),
    path("phieu/<int:pk>/", views.receipt_detail, name="inventory_receipt"),
]
