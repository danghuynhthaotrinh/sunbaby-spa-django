from django.db import models
from django.conf import settings

class DamageReport(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Chờ duyệt'),
        ('APPROVED', 'Đã duyệt xuất hủy'),
        ('REJECTED', 'Từ chối'),
    ]
    report_code = models.CharField(max_length=50, unique=True)
    item = models.ForeignKey('inventory.Item', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255)
    image_url = models.CharField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'damage_reports'

class PurchaseOrder(models.Model):
    po_code = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT)
    item = models.ForeignKey('inventory.Item', on_delete=models.PROTECT)
    suggested_qty = models.DecimalField(max_digits=10, decimal_places=2)
    actual_qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'purchase_orders'
