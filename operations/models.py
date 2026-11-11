from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from inventory.models import Item, Supplier

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
    item = models.OneToOneField(Item, on_delete=models.CASCADE, related_name='linen_tracking')
    clean_qty = models.PositiveIntegerField(default=0)
    in_service_qty = models.PositiveIntegerField(default=0)
    dirty_qty = models.PositiveIntegerField(default=0)
    laundry_qty = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'linen_tracking'

    @property
    def total_assets(self):
        return self.clean_qty + self.in_service_qty + self.dirty_qty + self.laundry_qty

    @property
    def stock_status(self):
        return 'Sắp thiếu' if self.clean_qty < self.item.min_stock else 'Đủ tồn'

    def clean(self):
        if self.item_id and not self.item.is_linen:
            raise ValidationError({'item': 'Chỉ mặt hàng is_linen=True được theo dõi đồ vải.'})

class LaundryShipment(models.Model):
    """Header phiếu nhiều SKU. Các cột item/SL trong bản đặc tả được chuyển xuống Detail."""
    class Status(models.TextChoices):
        SENT = 'SENT', 'Đang giặt tại xưởng'
        DISCREPANCY = 'DISCREPANCY', 'Nhận một phần'
        COMPLETED = 'COMPLETED', 'Đã hoàn tất'

    shipment_code = models.CharField(max_length=50, unique=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='laundry_shipments')
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='responsible_shipments')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='created_shipments')
    sent_at = models.DateTimeField(null=True, blank=True)
    expected_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    unit_price = models.PositiveIntegerField(default=5000, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=0, editable=False)
    is_legacy = models.BooleanField(default=False, editable=False)

    class Meta:
        db_table = 'laundry_shipments'
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(condition=Q(expected_at__isnull=True) | Q(expected_at__gt=F('sent_at')), name='laundry_deadline_valid'),
            models.CheckConstraint(condition=Q(unit_price=5000), name='laundry_fixed_price'),
            models.CheckConstraint(condition=Q(status__in=['SENT', 'DISCREPANCY', 'COMPLETED']), name='laundry_status_valid'),
            models.CheckConstraint(condition=Q(is_legacy=True) | Q(status='SENT', received_at__isnull=True) | Q(status__in=['DISCREPANCY', 'COMPLETED'], received_at__isnull=False), name='laundry_receipt_time_valid'),
        ]

    def clean(self):
        if self.supplier_id and self.supplier.supplier_type != 'LAUNDRY':
            raise ValidationError({'supplier': 'Đối tác phải là xưởng giặt.'})
        if self.sent_at and self.expected_at and self.expected_at <= self.sent_at:
            raise ValidationError({'expected_at': 'Hạn nhận phải sau ngày giờ giao.'})

    @property
    def sent_qty(self):
        return sum(d.sent_qty for d in self.details.all())

    @property
    def received_qty(self):
        return sum(d.received_qty for d in self.details.all())

    @property
    def loss_qty(self):
        return 0 if self.status == self.Status.SENT else self.sent_qty - self.received_qty

    @property
    def laundry_cost(self):
        return self.sent_qty * self.unit_price

    def __str__(self):
        return self.shipment_code

class LaundryShipmentDetail(models.Model):
    shipment = models.ForeignKey(LaundryShipment, on_delete=models.CASCADE, related_name='details')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='laundry_details')
    sent_qty = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    received_qty = models.PositiveIntegerField(default=0)
    loss_note = models.CharField(max_length=250, blank=True, default='')

    class Meta:
        db_table = 'laundry_shipment_details'
        constraints = [
            models.UniqueConstraint(fields=['shipment', 'item'], name='laundry_shipment_item_unique'),
            models.CheckConstraint(condition=Q(sent_qty__gt=0), name='laundry_sent_positive'),
            models.CheckConstraint(condition=Q(received_qty__lte=F('sent_qty')), name='laundry_received_valid'),
        ]

    @property
    def loss_qty(self):
        return 0 if self.shipment.status == LaundryShipment.Status.SENT else self.sent_qty - self.received_qty

    def clean(self):
        if self.item_id and not self.item.is_linen:
            raise ValidationError({'item': 'Phiếu giặt chỉ được chứa đồ vải.'})
        if (self.shipment_id and self.shipment.status != LaundryShipment.Status.SENT
                and self.received_qty is not None and self.sent_qty is not None
                and self.received_qty < self.sent_qty and not self.loss_note.strip()):
            raise ValidationError({'loss_note': 'Cần ghi chú khi có thất thoát.'})

class DocumentSequence(models.Model):
    """Bảng kỹ thuật cấp mã theo loại chứng từ và ngày lập."""
    prefix = models.CharField(max_length=10)
    date = models.DateField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'operations_document_sequences'
        constraints = [models.UniqueConstraint(fields=['prefix', 'date'], name='ops_sequence_unique')]
class LinenItem(models.Model):
    item = models.OneToOneField('inventory.Item', on_delete=models.CASCADE, related_name='linen_item_uc6')
    damaged_qty = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.item.name} - Hỏng: {self.damaged_qty}"
