# -*- coding: utf-8 -*-
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.db import models, transaction

class NhaCungCap(models.Model):
    ma_ncc = models.CharField(max_length=30, unique=True)
    ten = models.CharField(max_length=200)
    sdt = models.CharField(max_length=30, blank=True)
    dia_chi = models.TextField(blank=True)

    def __str__(self):
        return f"{self.ma_ncc} - {self.ten}"


class NhomVatTu(models.Model):
    ma_nhom = models.CharField(max_length=30, unique=True)
    ten = models.CharField(max_length=200)

    def __str__(self):
        return self.ten


class VatTu(models.Model):
    sku = models.CharField(max_length=50, unique=True, error_messages={"unique": "Mã SKU vật tư đã tồn tại!"})
    ten = models.CharField(max_length=255)
    nhom = models.ForeignKey(NhomVatTu, on_delete=models.PROTECT, related_name="vat_tus")
    don_vi_nhap = models.CharField(max_length=50)
    don_vi_chuan = models.CharField(max_length=50)
    ty_le_quy_doi = models.DecimalField(max_digits=14, decimal_places=3)
    don_gia_nhap = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    ton_toi_thieu = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    ton_kha_dung = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    la_do_vai = models.BooleanField(default=False)
    ncc_mac_dinh = models.ForeignKey(NhaCungCap, null=True, blank=True, on_delete=models.SET_NULL)

    def clean(self):
        errors = {}
        if self.ty_le_quy_doi is None or self.ty_le_quy_doi <= 0:
            errors["ty_le_quy_doi"] = "Tỷ lệ quy đổi giữa đơn vị nhập và đơn vị chuẩn phải là số dương lớn hơn 0!"
        if self.don_gia_nhap is not None and self.don_gia_nhap < 0:
            errors["don_gia_nhap"] = "Đơn giá nhập phải không âm."
        if self.ton_toi_thieu is not None and self.ton_toi_thieu < 0:
            errors["ton_toi_thieu"] = "Tồn tối thiểu phải không âm."
        if errors:
            raise ValidationError(errors)

    @property
    def gia_von_don_vi_chuan(self):
        return self.don_gia_nhap / self.ty_le_quy_doi if self.ty_le_quy_doi else Decimal("0")

    def __str__(self):
        return f"{self.sku} - {self.ten}"


class PhieuNhap(models.Model):
    ma_phieu = models.CharField(max_length=20, unique=True, blank=True)
    ncc = models.ForeignKey(NhaCungCap, on_delete=models.PROTECT)
    nguoi_nhap = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    ngay_nhap = models.DateTimeField(default=timezone.now)
    hinh_thuc_thanh_toan = models.CharField(max_length=100)
    ghi_chu = models.TextField(blank=True)
    trang_thai = models.CharField(max_length=50, default="Đã nhập kho đủ")

    def save(self, *args, **kwargs):
        if not self.ma_phieu:
            ngay = timezone.localdate().strftime("%Y%m%d")
            prefix = f"PN-{ngay}-"
            with transaction.atomic():
                last = PhieuNhap.objects.filter(ma_phieu__startswith=prefix).order_by("-ma_phieu").first()
                self.ma_phieu = f"{prefix}{(int(last.ma_phieu[-3:]) + 1 if last else 1):03d}"
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    @property
    def tong_tien(self):
        return sum((dong.thanh_tien for dong in self.dong_hang.all()), Decimal("0"))


class DongPhieuNhap(models.Model):
    phieu = models.ForeignKey(PhieuNhap, on_delete=models.CASCADE, related_name="dong_hang")
    vat_tu = models.ForeignKey(VatTu, on_delete=models.PROTECT)
    so_luong_nhap = models.DecimalField(max_digits=14, decimal_places=3)
    don_gia_mua = models.DecimalField(max_digits=18, decimal_places=2)
    han_su_dung = models.DateField(null=True, blank=True)

    @property
    def thanh_tien(self):
        return self.so_luong_nhap * self.don_gia_mua

    @property
    def so_luong_quy_doi(self):
        return self.so_luong_nhap * self.vat_tu.ty_le_quy_doi


class TheKho(models.Model):
    vat_tu = models.ForeignKey(VatTu, on_delete=models.PROTECT, related_name="the_kho")
    ngay = models.DateTimeField(default=timezone.now)
    loai_bien_dong = models.CharField(max_length=50, default="Nhập mua NCC")
    so_luong = models.DecimalField(max_digits=14, decimal_places=3)
    ton_cuoi = models.DecimalField(max_digits=14, decimal_places=3)
    chung_tu = models.CharField(max_length=30)
