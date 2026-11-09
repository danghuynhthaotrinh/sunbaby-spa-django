from django.contrib import admin
from .models import Supplier, Item, GoodsReceipt, GoodsReceiptDetail

admin.site.register(Supplier)
admin.site.register(Item)
admin.site.register(GoodsReceipt)
admin.site.register(GoodsReceiptDetail)

