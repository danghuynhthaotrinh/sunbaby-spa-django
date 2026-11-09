from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

CATEGORIES = {"CAT-OIL": "Tinh dầu & Kem mỹ phẩm", "CAT-LIN": "Đồ vải luân chuyển", "CAT-DIS": "Vật tư tiêu hao 1 lần", "CAT-BEA": "Phụ liệu chăm sóc chuyên sâu", "CAT-FNB": "Đồ uống & Tiếp đón"}


class Supplier(models.Model):
    TYPE_CHOICES = [("GOODS", "Cung cấp hàng hóa"), ("LAUNDRY", "Xưởng giặt ủi")]
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=100, null=True, blank=True)
    supplier_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="GOODS")

    class Meta:
        db_table = "suppliers"


class Item(models.Model):
    sku = models.CharField(
        max_length=50, unique=True,
        error_messages={"unique": "Mã SKU vật tư đã tồn tại!"},
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    standard_unit = models.CharField(max_length=50)
    import_unit = models.CharField(max_length=50, null=True, blank=True)
    conversion_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=1.0,
        validators=[MinValueValidator(
            Decimal("0.01"),
            message="Tỷ lệ quy đổi giữa đơn vị nhập và đơn vị chuẩn phải là số dương lớn hơn 0!",
        )],
    )
    stock = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    min_stock = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.0,
        validators=[MinValueValidator(0)],
    )
    is_linen = models.BooleanField(default=False)
    import_price = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        db_table = "items"

    def __str__(self):
        return f"{self.sku} - {self.name}"


class GoodsReceipt(models.Model):
    receipt_code = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=50, default="Đã nhập kho đủ")

    class Meta:
        db_table = "goods_receipts"


class GoodsReceiptDetail(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="details")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    import_qty = models.DecimalField(max_digits=10, decimal_places=2)
    conversion_rate = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)
    converted_qty = models.DecimalField(max_digits=12, decimal_places=2)
    import_price = models.DecimalField(max_digits=18, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "goods_receipt_details"


class TheKho(models.Model):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="the_kho")
    ngay = models.DateTimeField(default=timezone.now)
    loai_bien_dong = models.CharField(max_length=50, default="Nhập mua NCC")
    so_luong = models.DecimalField(max_digits=14, decimal_places=3)
    ton_cuoi = models.DecimalField(max_digits=14, decimal_places=3)
    chung_tu = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.item.sku} - {self.chung_tu}"
