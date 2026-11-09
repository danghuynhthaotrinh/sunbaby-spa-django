# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import NhaCungCap, NhomVatTu, VatTu, PhieuNhap, DongPhieuNhap, TheKho

for model in (NhaCungCap, NhomVatTu, VatTu, PhieuNhap, DongPhieuNhap, TheKho):
    admin.site.register(model)
