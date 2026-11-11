from decimal import Decimal
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone

from .models import DamageReport, PurchaseOrder, PurchaseOrderDetail
from inventory.models import Item, Supplier, TheKho
from operations.models import LinenItem


def is_manager_or_admin(user):
    return user.is_authenticated and (user.role in ['ADMIN', 'MANAGER'] or user.is_superuser)


def deny_access(request):
    messages.error(request, "Bạn không đủ quyền truy cập")
    return render(request, 'accounts/no_permission.html', {
        'error_message': 'Bạn không đủ quyền truy cập'
    }, status=403)


@login_required(login_url='login')
def management_entry(request):
    """UC_6: Điểm vào menu Báo hỏng & Điều hành - Điều hướng theo vai trò"""
    if is_manager_or_admin(request.user):
        return redirect('uc6_dashboard')
    return redirect('damage_create')


# ==========================================
# UC_6.1: TẠO PHIẾU BÁO HỎNG (Mọi vai trò)
# ==========================================
@login_required(login_url='login')
def damage_create(request):
    items = Item.objects.all().order_by('name')
    my_reports = DamageReport.objects.filter(reported_by=request.user).select_related('item', 'approved_by')[:10]

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        quantity_str = request.POST.get('quantity', '').strip()
        severity = request.POST.get('severity', 'MEDIUM')
        reason = request.POST.get('reason', '').strip()
        evidence_image = request.FILES.get('evidence_image')

        # Exception 6a: Kiểm tra thiếu trường bắt buộc
        if not item_id or not quantity_str or not reason:
            messages.error(request, "Vui lòng nhập đầy đủ đối tượng hỏng, số lượng và mô tả tình trạng!")
            return render(request, 'management/damage_create.html', {
                'items': items, 'my_reports': my_reports, 'active_tab': 'create'
            })

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Số lượng báo hỏng phải là số nguyên lớn hơn 0.")
            return render(request, 'management/damage_create.html', {
                'items': items, 'my_reports': my_reports, 'active_tab': 'create'
            })

        item = get_object_or_404(Item, pk=item_id)
        report = DamageReport.objects.create(
            item=item,
            reported_by=request.user,
            quantity=quantity,
            severity=severity,
            reason=reason,
            evidence_image=evidence_image,
            status='PENDING'
        )
        messages.success(request, f"Đã gửi phiếu báo hỏng #{report.id} ({item.name}) ở trạng thái Chờ duyệt.")
        return redirect('damage_create')

    return render(request, 'management/damage_create.html', {
        'items': items,
        'my_reports': my_reports,
        'active_tab': 'create'
    })


# ==========================================
# UC_6.2: DUYỆT PHIẾU BÁO HỎNG (Quản lý/Admin)
# ==========================================
@login_required(login_url='login')
def damage_review_list(request):
    if not is_manager_or_admin(request.user):
        return deny_access(request)

    status_filter = request.GET.get('status', 'PENDING')
    reports = DamageReport.objects.select_related('item', 'reported_by', 'approved_by').all()
    if status_filter != 'ALL':
        reports = reports.filter(status=status_filter)

    selected_id = request.GET.get('selected')
    selected_report = None
    if selected_id:
        selected_report = reports.filter(pk=selected_id).first() or DamageReport.objects.filter(pk=selected_id).first()
    elif reports.exists():
        selected_report = reports.first()

    counts = {
        'pending': DamageReport.objects.filter(status='PENDING').count(),
        'approved': DamageReport.objects.filter(status='APPROVED').count(),
        'rejected': DamageReport.objects.filter(status='REJECTED').count(),
    }

    return render(request, 'management/damage_review.html', {
        'reports': reports,
        'selected_report': selected_report,
        'status_filter': status_filter,
        'counts': counts,
        'active_tab': 'review'
    })


@login_required(login_url='login')
@transaction.atomic
def damage_review_action(request, pk):
    if not is_manager_or_admin(request.user):
        return deny_access(request)

    if request.method != 'POST':
        return redirect('damage_review_list')

    report = get_object_or_404(DamageReport.objects.select_for_update(), pk=pk)

    # Exception 3a: Phiếu đã được người khác xử lý trước đó
    if report.status != 'PENDING':
        messages.warning(request, f"Phiếu #{report.id} không còn ở trạng thái chờ duyệt (đã được xử lý trước đó).")
        return redirect('damage_review_list')

    action = request.POST.get('action')

    if action == 'approve':
        item = Item.objects.select_for_update().get(pk=report.item_id)
        deduct_qty = int(report.quantity)

        # 1. Trừ tồn kho (sử dụng trường stock)
        item.stock = max(0, item.stock - deduct_qty)
        item.save(update_fields=['stock'])

        # 2. Ghi thẻ kho (TheKho)
        TheKho.objects.create(
            item=item,
            loai='XUAT',
            so_luong=Decimal(str(deduct_qty)),
            ton_sau=Decimal(str(item.stock)),
            tham_chieu=f"DAMAGE-{report.id}",
            ghi_chu=f"Trừ kho do duyệt báo hỏng #{report.id}: {report.reason}"
        )

        # 3. Nếu là Đồ vải (LINEN), cập nhật số lượng vải hỏng trong bảng LinenItem
        if item.category == 'LINEN':
            linen_obj, _ = LinenItem.objects.get_or_create(item=item)
            linen_obj.damaged_qty += report.quantity
            linen_obj.save(update_fields=['damaged_qty'])

        # 4. Cập nhật trạng thái phiếu
        report.status = 'APPROVED'
        report.approved_by = request.user
        report.reviewed_at = timezone.now()
        report.save()

        messages.success(
            request,
            f"Đã duyệt phiếu #{report.id}! Đã trừ {report.quantity} {item.unit_usage if hasattr(item, 'unit_usage') else ''} khỏi kho. "
            f"Bạn có thể bấm 'Tạo PO bổ sung' bên dưới để đặt mua bù."
        )
        return redirect(f"/management/review/?status=APPROVED&selected={report.id}")

    elif action == 'reject':
        reject_reason = request.POST.get('reject_reason', '').strip()
        if not reject_reason:
            messages.error(request, "Vui lòng nhập lý do từ chối phiếu báo hỏng!")
            return redirect(f"/management/review/?status=PENDING&selected={report.id}")

        report.status = 'REJECTED'
        report.reject_reason = reject_reason
        report.approved_by = request.user
        report.reviewed_at = timezone.now()
        report.save()

        messages.info(request, f"Đã từ chối phiếu báo hỏng #{report.id}.")
        return redirect(f"/management/review/?status=REJECTED&selected={report.id}")

    return redirect('damage_review_list')


# ==========================================
# UC_6.3: ĐƠN MUA HÀNG PO (Quản lý/Admin)
# ==========================================
@login_required(login_url='login')
@transaction.atomic
def po_list_create(request):
    if not is_manager_or_admin(request.user):
        return deny_access(request)

    suppliers = Supplier.objects.all().order_by('name')
    items = Item.objects.all().order_by('name')
    pos = PurchaseOrder.objects.select_related('supplier', 'created_by', 'damage_report').prefetch_related('details__item').all()

    # Hỗ trợ tự động điền khi chuyển sang từ phiếu báo hỏng hoặc cảnh báo tồn kho
    from_damage_id = request.GET.get('from_damage')
    from_item_id = request.GET.get('from_item')
    prefill = {'source': 'MANUAL', 'damage_report': None, 'item': None, 'qty': 10}

    if from_damage_id:
        dr = DamageReport.objects.select_related('item').filter(pk=from_damage_id).first()
        if dr:
            prefill = {'source': 'DAMAGE', 'damage_report': dr, 'item': dr.item, 'qty': dr.quantity}
    elif from_item_id:
        it = Item.objects.filter(pk=from_item_id).first()
        if it:
            suggest_qty = max(1, int(it.min_stock * 2 - it.stock))
            prefill = {'source': 'LOW_STOCK', 'damage_report': None, 'item': it, 'qty': suggest_qty}

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        source = request.POST.get('source', 'MANUAL')
        damage_report_id = request.POST.get('damage_report_id') or None
        note = request.POST.get('note', '').strip()

        item_ids = request.POST.getlist('item_id[]')
        quantities = request.POST.getlist('quantity[]')
        unit_prices = request.POST.getlist('unit_price[]')

        valid_lines = []
        for i_id, q_str, p_str in zip(item_ids, quantities, unit_prices):
            if i_id and q_str and p_str:
                try:
                    q = int(q_str)
                    p = Decimal(str(p_str))
                    if q > 0 and p >= 0:
                        valid_lines.append((int(i_id), q, p))
                except ValueError:
                    continue

        # Exception 8a: Thiếu nhà cung cấp hoặc dòng vật tư
        if not supplier_id or not valid_lines:
            messages.error(request, "Vui lòng chọn Nhà cung cấp và thêm ít nhất 1 dòng vật tư hợp lệ!")
            return render(request, 'management/po_manage.html', {
                'suppliers': suppliers, 'items': items, 'pos': pos, 'prefill': prefill, 'active_tab': 'po'
            })

        supplier = get_object_or_404(Supplier, pk=supplier_id)
        total_amount = sum(q * p for _, q, p in valid_lines)

        po = PurchaseOrder.objects.create(
            supplier=supplier,
            created_by=request.user,
            status='DRAFT',
            source=source,
            damage_report_id=damage_report_id,
            total_amount=total_amount,
            note=note
        )

        for i_id, q, p in valid_lines:
            PurchaseOrderDetail.objects.create(
                po=po,
                item_id=i_id,
                quantity=q,
                unit_price=p
            )

        messages.success(request, f"Đã tạo đơn mua hàng PO-{po.id:04d} thành công! Tổng tiền: {total_amount:,.0f} đ.")
        return redirect('po_list_create')

    return render(request, 'management/po_manage.html', {
        'suppliers': suppliers,
        'items': items,
        'pos': pos,
        'prefill': prefill,
        'active_tab': 'po'
    })


@login_required(login_url='login')
def po_update_status(request, pk):
    if not is_manager_or_admin(request.user):
        return deny_access(request)

    if request.method == 'POST':
        po = get_object_or_404(PurchaseOrder, pk=pk)
        new_status = request.POST.get('status')
        if new_status in dict(PurchaseOrder.STATUS_CHOICES):
            po.status = new_status
            po.save(update_fields=['status'])
            messages.success(request, f"Đã cập nhật trạng thái PO-{po.id:04d} sang '{po.get_status_display()}'.")
    return redirect('po_list_create')


# ==========================================
# UC_6.4: DASHBOARD ĐIỀU HÀNH (Quản lý/Admin)
# ==========================================
@login_required(login_url='login')
def uc6_dashboard(request):
    if not is_manager_or_admin(request.user):
        return deny_access(request)

    # Bộ lọc khoảng thời gian (Alternative flow 3a)
    days_filter = request.GET.get('days', '30')
    try:
        days = int(days_filter)
    except ValueError:
        days = 30
    since_date = timezone.now() - timedelta(days=days)

    # 1. Thống kê Phiếu báo hỏng chờ duyệt & trong kỳ
    pending_damages_count = DamageReport.objects.filter(status='PENDING').count()
    recent_damages = DamageReport.objects.select_related('item', 'reported_by').filter(created_at__gte=since_date)[:6]

    # 2. Thống kê PO đang xử lý
    processing_pos_count = PurchaseOrder.objects.filter(status__in=['DRAFT', 'SENT']).count()
    total_po_value = PurchaseOrder.objects.filter(
        created_at__gte=since_date
    ).exclude(status='CANCELLED').aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

    # 3. Cảnh báo vật tư chạm ngưỡng an toàn (min_stock sử dụng trường stock)
    low_stock_items = Item.objects.filter(stock__lte=F('min_stock')).order_by('stock')

    # 4. Hàng tồn lâu ngày (không có giao dịch xuất kho trong N ngày)
    active_item_ids = TheKho.objects.filter(
        ngay__gte=since_date
    ).values_list('item_id', flat=True).distinct()
    slow_moving_items = Item.objects.filter(stock__gt=0).exclude(id__in=active_item_ids)[:8]

    return render(request, 'management/dashboard.html', {
        'days': days,
        'pending_damages_count': pending_damages_count,
        'processing_pos_count': processing_pos_count,
        'total_po_value': total_po_value,
        'low_stock_count': low_stock_items.count(),
        'low_stock_items': low_stock_items[:6],
        'slow_moving_items': slow_moving_items,
        'recent_damages': recent_damages,
        'active_tab': 'dashboard',
    })
