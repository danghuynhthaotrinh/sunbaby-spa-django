from django.db import models
from django.conf import settings
from inventory.models import Item, Supplier

class DamageReport(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Chờ duyệt'),
        ('APPROVED', 'Đã duyệt'),
        ('REJECTED', 'Từ chối'),
    ]
    SEVERITY_CHOICES = [
        ('LOW', 'Nhẹ (Có thể sửa/giặt lại)'),
        ('MEDIUM', 'Trung bình (Hư hại một phần)'),
        ('HIGH', 'Nặng (Hỏng hoàn toàn - Cần thanh lý)'),
    ]

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='damage_reports', verbose_name="Đối tượng hỏng")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reported_damages', verbose_name="Người lập",null=True,
    blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_damages', verbose_name="Người duyệt")
    quantity = models.IntegerField(verbose_name="Số lượng hỏng")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM', verbose_name="Mức độ hỏng")
    reason = models.TextField(verbose_name="Mô tả tình trạng")
    reject_reason = models.TextField(blank=True, null=True, verbose_name="Lý do từ chối")
    evidence_image = models.ImageField(upload_to='damage_evidences/', blank=True, null=True, verbose_name="Ảnh minh chứng")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Trạng thái")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian lập")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian duyệt")

    class Meta:
        db_table = 'damage_reports'
        ordering = ['-created_at']

    def __str__(self):
        return f"Phiếu hỏng #{self.id} - {self.item.name}"


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Nháp / Chờ gửi'),
        ('SENT', 'Đã gửi NCC'),
        ('COMPLETED', 'Đã nhận hàng'),
        ('CANCELLED', 'Đã hủy'),
    ]
    SOURCE_CHOICES = [
        ('MANUAL', 'Tạo thủ công'),
        ('DAMAGE', 'Từ phiếu báo hỏng'),
        ('LOW_STOCK', 'Từ cảnh báo tồn kho'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders', verbose_name="Nhà cung cấp")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Người lập")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="Trạng thái")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='MANUAL', verbose_name="Nguồn tạo PO")
    damage_report = models.ForeignKey(DamageReport, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Tổng tiền")
    note = models.TextField(blank=True, null=True, verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = 'purchase_orders'
        ordering = ['-created_at']

    def __str__(self):
        return f"PO-{self.id:04d} ({self.supplier.name})"


class PurchaseOrderDetail(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='details')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'purchase_order_details'

    @property
    def subtotal(self):
        return self.quantity * self.unit_price
