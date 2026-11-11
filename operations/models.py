from django.db import models
from django.conf import settings

class ServiceOrder(models.Model):
    STATUS_CHOICES = [
        ('SERVING', 'Đang phục vụ'),
        ('COMPLETED', 'Hoàn tất'),
        ('CANCELLED', 'Đã hủy'),
    ]
    order_code = models.CharField(max_length=50, unique=True)
    service = models.ForeignKey('services.ServicePackage', on_delete=models.PROTECT)
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    room = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SERVING')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'service_orders'

class LinenTracking(models.Model):
    item = models.OneToOneField('inventory.Item', on_delete=models.CASCADE, related_name='linen_tracking')
    clean_qty = models.IntegerField(default=0)
    in_service_qty = models.IntegerField(default=0)
    dirty_qty = models.IntegerField(default=0)
    laundry_qty = models.IntegerField(default=0)

    class Meta:
        db_table = 'linen_tracking'

class LaundryShipment(models.Model):
    STATUS_CHOICES = [
        ('SENT', 'Đang ở xưởng'),
        ('COMPLETED', 'Nhận đủ'),
        ('DISCREPANCY', 'Bị lệch/mất đồ'),
    ]
    shipment_code = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT)
    item = models.ForeignKey('inventory.Item', on_delete=models.PROTECT)
    sent_qty = models.IntegerField()
    received_qty = models.IntegerField(default=0)
    loss_qty = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'laundry_shipments'
from django.db import models
from inventory.models import Item

class LinenItem(models.Model):
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='linen_spec')
    total_qty = models.IntegerField(default=0, verbose_name="Tổng số lượng")
    damaged_qty = models.IntegerField(default=0, verbose_name="Số lượng hỏng")
    in_use_qty = models.IntegerField(default=0, verbose_name="Đang sử dụng/Giặt")

    class Meta:
        db_table = 'linen_items'

    def __str__(self):
        return f"Đồ vải: {self.item.name} (Hỏng: {self.damaged_qty})"
