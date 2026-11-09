from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from inventory.models import Item


class ServicePackage(models.Model):
    NHOM_CHOICES = [
        ("MASSAGE", "Massage"),
        ("CHAM_SOC", "Chăm sóc da"),
        ("TAM", "Tắm & thư giãn"),
        ("KHAC", "Khác"),
    ]

    ma_goi = models.CharField("Mã gói", max_length=20, unique=True)
    ten = models.CharField("Tên gói", max_length=200)
    nhom = models.CharField("Nhóm", max_length=20, choices=NHOM_CHOICES, default="MASSAGE")
    thoi_luong_phut = models.PositiveIntegerField("Thời lượng (phút)", default=60)
    gia_ban = models.DecimalField("Giá bán", max_digits=14, decimal_places=0,
                                  validators=[MinValueValidator(0)])
    mo_ta = models.TextField("Mô tả", blank=True)
    dang_ban = models.BooleanField("Đang bán", default=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ma_goi"]

    def __str__(self):
        return f"{self.ma_goi} - {self.ten}"

    @property
    def chi_phi_nguyen_vat(self):
        # Dùng .all() để tận dụng prefetch_related("bom_items__vat_tu") ở view
        return sum((d.chi_phi_dong for d in self.bom_items.all()), Decimal("0"))

    @property
    def ty_le_gia_von(self):
        if not self.gia_ban:
            return None
        return round(self.chi_phi_nguyen_vat / self.gia_ban * 100, 1)

    @property
    def trang_thai_gia(self):
        """CHUA_BOM / THIEU_GIA / DA_TINH"""
        dong = list(self.bom_items.all())
        if not dong:
            return "CHUA_BOM"
        if any(d.thieu_don_gia for d in dong):
            return "THIEU_GIA"
        return "DA_TINH"


class BOMItem(models.Model):
    goi = models.ForeignKey(ServicePackage, related_name="bom_items",
                            on_delete=models.CASCADE)
    vat_tu = models.ForeignKey(Item, on_delete=models.PROTECT, verbose_name="Vật tư")
    dinh_luong = models.DecimalField("Định lượng (ĐV chuẩn)", max_digits=12,
                                     decimal_places=2,
                                     validators=[MinValueValidator(Decimal("0.01"))])
    ghi_chu = models.CharField("Ghi chú", max_length=200, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["goi", "vat_tu"], name="uniq_goi_vat_tu"),
        ]

    def __str__(self):
        return f"{self.goi.ma_goi}: {self.vat_tu} x {self.dinh_luong}"

    @property
    def thieu_don_gia(self):
        v = self.vat_tu
        return not v.import_price or not v.conversion_rate

    @property
    def gia_von_don_vi(self):
        rate = self.vat_tu.conversion_rate
        if not rate:
            return Decimal("0")
        return (self.vat_tu.import_price or Decimal("0")) / rate

    @property
    def chi_phi_dong(self):
        return self.dinh_luong * self.gia_von_don_vi