"""Lớp truy vấn dùng cho bảng tổng quan, danh sách và modal chi tiết."""
from .models import LinenTracking, LaundryShipment, LaundryShipmentDetail
from inventory.models import Item
from .permissions import require_user


class LinenQueries:
    @staticmethod
    def board(*, user, keyword=''):
        require_user(user, management=True)
        tracked = {row.item_id: row for row in LinenTracking.objects.select_related('item')}
        rows = [tracked.get(item.pk) or LinenTracking(item=item, clean_qty=int(item.stock))
                for item in Item.objects.filter(is_linen=True).order_by('sku')]
        losses = {}
        for detail in LaundryShipmentDetail.objects.exclude(shipment__status=LaundryShipment.Status.SENT):
            losses[detail.item_id] = losses.get(detail.item_id, 0) + detail.sent_qty-detail.received_qty
        term = keyword.strip().casefold()
        data = [dict(item_id=r.item_id, sku=r.item.sku, name=r.item.name,
            clean_qty=r.clean_qty, dirty_qty=r.dirty_qty, laundry_qty=r.laundry_qty,
            in_service_qty=r.in_service_qty, total_assets=r.total_assets,
            accumulated_loss=losses.get(r.item_id, 0), min_stock=r.item.min_stock,
            status=r.stock_status) for r in rows
            if term in r.item.sku.casefold() or term in r.item.name.casefold()]
        return dict(cards={key: sum(getattr(r, key) for r in rows)
                           for key in ['clean_qty', 'dirty_qty', 'laundry_qty']},
                    rows=data, message='' if data else 'Không tìm thấy đồ vải phù hợp.')

    @staticmethod
    def shipments(*, user):
        require_user(user, management=True)
        return LaundryShipment.objects.select_related('supplier', 'responsible').prefetch_related('details__item')

    @staticmethod
    def detail(*, user, shipment_id, for_receiving=False):
        shipment = LinenQueries.shipments(user=user).get(pk=shipment_id)
        editable = for_receiving and shipment.status != shipment.Status.COMPLETED
        first = shipment.status == shipment.Status.SENT
        return dict(shipment=shipment, editable=editable, version=shipment.version,
            rows=[dict(item_id=d.item_id, sku=d.item.sku, name=d.item.name,
                sent_qty=d.sent_qty, received_qty=d.sent_qty if editable and first else d.received_qty,
                loss_qty=d.loss_qty, loss_note=d.loss_note) for d in shipment.details.all()])

    @staticmethod
    def loss_summary(*, user):
        shipments = list(LinenQueries.shipments(user=user).filter(status=LaundryShipment.Status.DISCREPANCY))
        return dict(missing_qty=sum(s.loss_qty for s in shipments), shipment_count=len(shipments))
