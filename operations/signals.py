"""Đồng bộ tồn sạch khi phân hệ kho lưu lại tồn khả dụng của Item."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from inventory.models import Item
from .models import LinenTracking
from .validators import is_whole


@receiver(pre_save, sender=Item)
def validate_linen_stock(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or not instance.is_linen:
        return
    if update_fields is not None and not {'stock', 'is_linen'} & set(update_fields):
        return
    if not is_whole(instance.stock) or Decimal(str(instance.stock)) < 0:
        raise ValidationError({'stock': 'Tồn sạch đồ vải phải là số nguyên không âm.'})


@receiver(post_save, sender=Item)
def sync_clean_stock(sender, instance, raw=False, update_fields=None, using='default', **kwargs):
    if raw or not instance.is_linen:
        return
    if update_fields is not None and not {'stock', 'is_linen'} & set(update_fields):
        return
    # Không tạo/cập nhật các trạng thái bẩn/đang dùng/đang giặt bằng suy đoán.
    LinenTracking.objects.using(using).filter(item_id=instance.pk).exclude(
        clean_qty=int(instance.stock)).update(clean_qty=int(instance.stock))
