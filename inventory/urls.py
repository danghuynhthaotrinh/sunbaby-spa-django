from django.urls import path
<<<<<<< HEAD
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('', login_required(TemplateView.as_view(template_name='inventory/inventory_home.html'), login_url='login'), name='inventory_home'),
]
=======
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
>>>>>>> 8bf68790b21ce4b9c792b01e3b766464edc3a481
