"""UC_4 - Điều phối ca dịch vụ & tự động xuất kho theo BOM.

KHÔNG tạo lại bảng của người khác, chỉ dùng lại:
  * operations.ServiceOrder / operations.LinenTracking   (bảng service_orders, linen_tracking)
  * inventory.Item / inventory.TheKho                    (tồn kho + thẻ kho)
  * services.ServicePackage / services.BOMItem           (gói + định mức)

App này chỉ thêm 2 bảng "phụ" gắn vào ServiceOrder để KHÔNG phải sửa model của Hiển:
  * ServiceOrderDetail : khách hàng, SĐT, yêu cầu đặc biệt, mã phiếu xuất kho
  * ServiceOrderLine   : ảnh chụp định mức đã trừ (để hoàn kho chính xác khi hủy ca)
"""
from django.conf import settings
from django.db import models

from inventory.models import Item
from operations.models import ServiceOrder


class ServiceOrderDetail(models.Model):
    order = models.OneToOneField(ServiceOrder, on_delete=models.CASCADE, related_name="detail")
    issue_code = models.CharField("Phiếu xuất kho nội bộ", max_length=50, blank=True)
    customer_name = models.CharField("Khách hàng", max_length=120, blank=True)
    customer_phone = models.CharField("SĐT", max_length=20, blank=True)
    note = models.CharField("Yêu cầu đặc biệt", max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    def __str__(self):
        return f"Chi tiết {self.order_id}"


class ServiceOrderLine(models.Model):
    order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, related_name="shift_lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="shift_lines")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    is_linen = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.order_id}: {self.item_id} x {self.quantity}"
