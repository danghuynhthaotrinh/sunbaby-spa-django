from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from inventory.models import Item, TheKho
from .models import LinenTracking, LaundryShipment, LaundryShipmentDetail, DocumentSequence
from .permissions import require_user
from .validators import integer_value, unique_lines, is_whole


def _next_code():
    date = timezone.localdate()
    counter, _ = DocumentSequence.objects.get_or_create(prefix='PGN', date=date)
    counter = DocumentSequence.objects.select_for_update().get(pk=counter.pk)
    prefix = f'PGN-{date:%y%m%d}-'
    codes = LaundryShipment.objects.filter(shipment_code__startswith=prefix).values_list('shipment_code', flat=True)
    used = [int(code[len(prefix):]) for code in codes if code[len(prefix):].isdigit()]
    counter.last_number = max([counter.last_number, *used])
    if counter.last_number >= 99:
        raise ValidationError('Đã hết số thứ tự phiếu giặt 2 chữ số trong ngày.')
    counter.last_number += 1
    counter.save(update_fields=['last_number'])
    return f'{prefix}{counter.last_number:02d}'

def _create(model, **kwargs):
    obj = model(**kwargs)
    obj.full_clean()
    obj.save()
    return obj

def _save(obj, **kwargs):
    obj.full_clean()
    obj.save(**kwargs)

def _ledger(item, delta, code, kind):
    TheKho.objects.create(item=item, so_luong=delta, ton_cuoi=item.stock,
                         chung_tu=code, loai_bien_dong=kind)

def _lock_items(ids):
    items = {x.pk: x for x in Item.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    if len(items) != len(set(ids)):
        raise ValidationError('Mặt hàng không tồn tại.')
    return items

def _linen(item):
    if not item.is_linen:
        raise ValidationError('Mặt hàng không phải đồ vải.')
    # Không tự đoán cơ cấu sạch/bẩn của dữ liệu nhập tay.
    try:
        tracking = LinenTracking.objects.select_for_update().get(item=item)
    except LinenTracking.DoesNotExist:
        if not is_whole(item.stock) or item.stock < 0:
            raise ValidationError('Tồn sạch đồ vải phải là số nguyên không âm.')
        tracking = _create(LinenTracking, item=item, clean_qty=int(item.stock))
    if Decimal(tracking.clean_qty) != item.stock:
        raise ValidationError('Tồn sạch và tồn khả dụng không khớp; cần kiểm tra dữ liệu.')
    return tracking

class LaundryService:
    @staticmethod
    @transaction.atomic
    def send(*, user, supplier_id, responsible_id, sent_at, expected_at, lines):
        """lines: [{item_id, sent_qty, dirty_qty_snapshot}]."""
        require_user(user, management=True)
        if not sent_at or not expected_at:
            raise ValidationError('Vui lòng chọn ngày giờ giao và hạn nhận.')
        if expected_at <= sent_at:
            raise ValidationError('Hạn nhận phải sau ngày giờ giao.')
        lines, ids = unique_lines(lines)
        items = _lock_items(ids)
        if not get_user_model().objects.filter(pk=responsible_id, is_active=True).exists():
            raise ValidationError('Người phụ trách không hợp lệ.')
        shipment = _create(LaundryShipment, shipment_code=_next_code(),
            supplier_id=supplier_id, responsible_id=responsible_id, created_by=user,
            sent_at=sent_at, expected_at=expected_at)
        for line in lines:
            item = items[line['item_id']]
            tracking = _linen(item)
            qty = integer_value(line.get('sent_qty'), 1)
            snapshot = line.get('dirty_qty_snapshot')
            if type(snapshot) is not int or snapshot != tracking.dirty_qty:
                raise ValidationError('Số lượng đồ bẩn đã thay đổi. Vui lòng kiểm tra lại.')
            if qty > tracking.dirty_qty:
                raise ValidationError(f'Vượt số đồ bẩn hiện có ({tracking.dirty_qty}).')
            _create(LaundryShipmentDetail, shipment=shipment, item=item, sent_qty=qty)
            tracking.dirty_qty -= qty
            tracking.laundry_qty += qty
            _save(tracking, update_fields=['dirty_qty', 'laundry_qty'])
        return shipment

    @staticmethod
    @transaction.atomic
    def receive(*, user, shipment_id, received_at, version, lines):
        """received_qty là tổng lũy kế, gửi đủ tất cả các dòng trong phiếu."""
        require_user(user, management=True)
        if not received_at:
            raise ValidationError('Vui lòng chọn ngày giờ nhận.')
        shipment = LaundryShipment.objects.select_for_update().get(pk=shipment_id)
        if shipment.status == LaundryShipment.Status.COMPLETED:
            raise ValidationError('Phiếu đã hoàn tất, chỉ được xem.')
        if type(version) is not int or version != shipment.version:
            raise ValidationError('Phiếu đã thay đổi. Vui lòng mở lại chi tiết phiếu.')
        lines, ids = unique_lines(lines)
        details = list(shipment.details.select_for_update().order_by('item_id'))
        if set(ids) != {d.item_id for d in details}:
            raise ValidationError('Phải gửi đủ các dòng trong phiếu.')
        items = _lock_items(ids)
        submitted = {line['item_id']: line for line in lines}
        first = shipment.status == shipment.Status.SENT
        missing = False
        for detail in details:
            line = submitted[detail.item_id]
            qty = integer_value(line.get('received_qty'), detail.received_qty, detail.sent_qty)
            note = line.get('loss_note', '')
            if not isinstance(note, str) or len(note) > 250:
                raise ValidationError('Ghi chú thất thoát tối đa 250 ký tự.')
            note = note.strip()
            if qty < detail.sent_qty:
                missing = True
                if not note:
                    raise ValidationError('Cần ghi chú khi có thất thoát.')
            item = items[detail.item_id]
            tracking = _linen(item)
            delta = qty - detail.received_qty
            tracking.clean_qty += delta
            if first:
                if tracking.laundry_qty < detail.sent_qty:
                    raise ValidationError('Tồn đang giặt không khớp dữ liệu phiếu.')
                tracking.laundry_qty -= detail.sent_qty  # UC_5.2.1 BR06.
            _save(tracking, update_fields=['clean_qty', 'laundry_qty'])
            item.stock += delta
            _save(item, update_fields=['stock'])
            if delta:
                _ledger(item, delta, shipment.shipment_code, 'Nhận đồ sạch')
            detail.received_qty = qty
            detail.loss_note = note
            _save(detail, update_fields=['received_qty', 'loss_note'])
        shipment.status = shipment.Status.DISCREPANCY if missing else shipment.Status.COMPLETED
        shipment.received_at = received_at
        shipment.version += 1
        _save(shipment, update_fields=['status', 'received_at', 'version'])
        return shipment
