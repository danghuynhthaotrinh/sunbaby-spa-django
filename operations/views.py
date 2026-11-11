"""Giao diện vận hành: board, xuất giặt, nhận sạch/đối soát."""
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from .permissions import require_user
from inventory.models import Item
from .models import DocumentSequence
from .models import LaundryShipment, LinenTracking
from .business import LaundryService
from .forms import ShipmentForm, ShipmentLineSet, ReceiveForm, ReceiveLineSet
from .selectors import LinenQueries


def operations_access(view):
    @wraps(view)
    @login_required(login_url='operations_login')
    def wrapped(request, *args, **kwargs):
        require_user(request.user, management=True)
        return view(request, *args, **kwargs)
    return wrapped


def preview_code():
    """Gợi ý để hiển thị, không cấp số hoặc ghi DB khi chỉ xem form."""
    date = timezone.localdate()
    prefix = f'PGN-{date:%y%m%d}-'
    sequence = DocumentSequence.objects.filter(prefix='PGN', date=date).first()
    codes = LaundryShipment.objects.filter(shipment_code__startswith=prefix).values_list('shipment_code', flat=True)
    used = [int(code[len(prefix):]) for code in codes if code[len(prefix):].isdigit()]
    number = max([sequence.last_number if sequence else 0, *used]) + 1
    return f'{prefix}{number:02d}' if number <= 99 else 'Đã hết số phiếu trong ngày'


def page_context(request, tab):
    context = {'tab': tab}
    if tab == 'board':
        context['board'] = LinenQueries.board(user=request.user)
    elif tab == 'send':
        records = {r.item_id: r for r in LinenTracking.objects.all()}
        context['linen_data'] = [dict(id=item.pk, sku=item.sku, name=item.name,
            dirty_qty=records[item.pk].dirty_qty if item.pk in records else 0)
            for item in Item.objects.filter(is_linen=True).order_by('sku')]
        context['preview_code'] = preview_code()
    else:
        context['shipments'] = Paginator(LinenQueries.shipments(user=request.user), 15).get_page(request.GET.get('page'))
        context['summary'] = LinenQueries.loss_summary(user=request.user)
    return context


@operations_access
def operations_home(request):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(['GET', 'POST'])
    tab = request.GET.get('tab', 'board')
    if tab not in ['board', 'send', 'receive']:
        tab = 'board'
    if request.method == 'POST':
        tab = 'send'
    context = page_context(request, tab)
    if tab == 'send':
        form = ShipmentForm(request.POST if request.method == 'POST' else None)
        lines = ShipmentLineSet(request.POST if request.method == 'POST' else None, prefix='send')
        if request.method == 'POST':
            header_ok, lines_ok = form.is_valid(), lines.is_valid()
            if header_ok and lines_ok:
                try:
                    LaundryService.send(user=request.user, supplier_id=form.cleaned_data['supplier'].pk,
                        responsible_id=form.cleaned_data['responsible'].pk,
                        sent_at=form.cleaned_data['sent_at'], expected_at=form.cleaned_data['expected_at'],
                        lines=[dict(item_id=f.cleaned_data['item'].pk, sent_qty=f.cleaned_data['sent_qty'],
                                    dirty_qty_snapshot=f.cleaned_data['dirty_qty_snapshot'])
                               for f in lines if not f.cleaned_data.get('DELETE')])
                except ValidationError as exc:
                    form.add_error(None, ' '.join(exc.messages))
                else:
                    messages.success(request, 'Đã xác nhận xuất giặt. Phiếu mới đã xuất hiện trong danh sách.')
                    return redirect(reverse('operations_home') + '?tab=receive')
        context.update(shipment_form=form, send_lines=lines)
    return render(request, 'operations/linen_home.html', context)


@operations_access
def shipment_detail(request, pk):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(['GET', 'POST'])
    shipment = get_object_or_404(LinenQueries.shipments(user=request.user), pk=pk)
    editing = (request.GET.get('receive') == '1' or request.method == 'POST') and shipment.status != 'COMPLETED'
    details = list(shipment.details.all())
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    form = lines = None
    if editing:
        first = shipment.status == 'SENT'
        initial = [dict(item_id=d.item_id, received_qty=d.sent_qty if first else d.received_qty,
                        loss_note=d.loss_note) for d in details]
        form = ReceiveForm(request.POST if request.method == 'POST' else None,
            initial={'received_at': timezone.localtime(), 'version': shipment.version})
        lines = ReceiveLineSet(request.POST if request.method == 'POST' else None,
            initial=initial, prefix='receive', details=details)
        if request.method == 'POST':
            header_ok, lines_ok = form.is_valid(), lines.is_valid()
            if header_ok and lines_ok:
                try:
                    updated = LaundryService.receive(user=request.user, shipment_id=shipment.pk,
                        received_at=form.cleaned_data['received_at'], version=form.cleaned_data['version'],
                        lines=[f.cleaned_data for f in lines])
                except ValidationError as exc:
                    form.add_error(None, ' '.join(exc.messages))
                else:
                    messages.success(request, 'Đã nhận hàng và đối soát khớp.' if updated.status == 'COMPLETED'
                                     else 'Đã ghi nhận hàng nhận một phần và thất thoát.')
                    url = reverse('operations_home') + '?tab=receive'
                    return JsonResponse({'redirect': url}) if ajax else redirect(url)
    elif request.method == 'POST':
        # Reject forged/repeated submissions for a completed order; never downgrade it.
        return JsonResponse({'error': 'Phiếu đã hoàn tất, chỉ được xem.'}, status=409)
    modal = dict(shipment=shipment, editing=editing, receipt_form=form, receive_lines=lines, details=details)
    status = 422 if request.method == 'POST' else 200
    if ajax:
        return render(request, 'operations/_shipment_modal.html', modal, status=status)
    context = page_context(request, 'receive')
    context['modal'] = modal
    return render(request, 'operations/linen_home.html', context, status=status)
