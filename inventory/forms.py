# -*- coding: utf-8 -*-
from django import forms
from django.forms import inlineformset_factory
from .models import Item, Supplier, GoodsReceipt, GoodsReceiptDetail

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["sku", "name", "category", "supplier", "import_unit", "standard_unit", "conversion_rate", "import_price", "min_stock", "stock", "is_linen"]

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["code", "name", "phone", "email", "supplier_type"]

class ReceiptForm(forms.ModelForm):
    class Meta:
        model = GoodsReceipt
        fields = ["supplier", "payment_method", "note"]

class ReceiptDetailForm(forms.ModelForm):
    class Meta:
        model = GoodsReceiptDetail
        fields = ["item", "import_qty", "import_price", "expiry_date"]

ReceiptDetailFormSet = inlineformset_factory(GoodsReceipt, GoodsReceiptDetail, form=ReceiptDetailForm, extra=3, can_delete=True)
