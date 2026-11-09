# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone
from inventory.models import Item

CATEGORIES = {
    "CAT-OIL": "Tinh dầu & Kem mỹ phẩm",
    "CAT-LIN": "Đồ vải luân chuyển",
    "CAT-DIS": "Vật tư tiêu hao 1 lần",
    "CAT-BEA": "Phụ liệu chăm sóc chuyên sâu",
    "CAT-FNB": "Đồ uống & Tiếp đón",
}


class TheKho(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="the_kho")
    ngay = models.DateTimeField(default=timezone.now)
    loai_bien_dong = models.CharField(max_length=50, default="Nhập mua NCC")
    so_luong = models.DecimalField(max_digits=14, decimal_places=3)
    ton_cuoi = models.DecimalField(max_digits=14, decimal_places=3)
    chung_tu = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.item.sku} - {self.chung_tu}"
