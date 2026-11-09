# -*- coding: utf-8 -*-
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import ItemForm, SupplierForm, ReceiptForm, ReceiptDetailFormSet
from .models import Item, Supplier, GoodsReceipt, GoodsReceiptDetail, TheKho, CATEGORIES

def access(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if getattr(request.user, "role", "") not in ("MANAGER", "ADMIN"):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped

@access
def inventory_home(request):
    items = Item.objects.select_related("supplier").all()
    query = request.GET.get("q", "")
    if query:
        items = items.filter(Q(sku__icontains=query) | Q(name__icontains=query))
    if request.GET.get("nhom"):
        items = items.filter(category=request.GET["nhom"])
    if request.GET.get("ncc"):
        items = items.filter(supplier_id=request.GET["ncc"])
    today = timezone.localdate()
    idle = []
    for item in Item.objects.filter(stock__gt=0):
        last_out = item.the_kho.filter(loai_bien_dong__icontains="xuất").order_by("-ngay").first()
        last_receipt = GoodsReceiptDetail.objects.filter(item=item).order_by("-receipt__created_at").first()
        last_date = last_out.ngay.date() if last_out else (last_receipt.receipt.created_at.date() if last_receipt else today)
        if (today - last_date).days >= 45:
            idle.append((item, (today - last_date).days))
    context = {
        "items": Paginator(items.order_by("sku"), 15).get_page(request.GET.get("page")),
        "q": query, "nhoms": CATEGORIES.items(), "nccs": Supplier.objects.all(),
        "n_vattu": Item.objects.count(), "n_ncc": Supplier.objects.count(),
        "low": Item.objects.filter(stock__lt=F("min_stock")).count(),
        "phieus": GoodsReceipt.objects.select_related("supplier", "created_by").order_by("-created_at"),
        "canh_bao": idle,
        "lo_han": GoodsReceiptDetail.objects.filter(expiry_date__range=(today, today + timedelta(days=30))).select_related("item"),
    }
    return render(request, "inventory/inventory_home.html", context)

@access
def item_form(request, pk=None):
    instance = get_object_or_404(Item, pk=pk) if pk else None
    form = ItemForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        messages.success(request, "Đã lưu vật tư.")
        return redirect("inventory_home")
    return render(request, "inventory/form.html", {"form": form, "title": "Cập nhật vật tư" if instance else "Thêm vật tư"})

@access
def item_delete(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Đã xóa vật tư.")
        return redirect("inventory_home")
    return render(request, "inventory/delete.html", {"obj": item})

@access
def supplier_form(request):
    form = SupplierForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Đã lưu nhà cung cấp.")
        return redirect("inventory_home")
    return render(request, "inventory/form.html", {"form": form, "title": "Nhà cung cấp"})

@access
def receive_goods(request):
    form = ReceiptForm(request.POST or None)
    instance = GoodsReceipt()
    formset = ReceiptDetailFormSet(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        rows = [row for row in formset.save(commit=False) if row.item_id and row.import_qty]
        if not rows:
            messages.error(request, "Phiếu nhập cần có ít nhất một dòng hàng.")
        elif any(row.import_qty <= 0 or row.import_price < 0 or row.item.conversion_rate <= 0 for row in rows):
            messages.error(request, "Số lượng phải dương, đơn giá không âm và tỷ lệ quy đổi phải dương.")
        else:
            with transaction.atomic():
                receipt = form.save(commit=False)
                receipt.created_by = request.user
                prefix = f"PN-{timezone.localdate():%Y%m%d}-"
                last = GoodsReceipt.objects.select_for_update().filter(receipt_code__startswith=prefix).order_by("-receipt_code").first()
                receipt.receipt_code = f"{prefix}{int(last.receipt_code[-3:]) + 1 if last else 1:03d}"
                receipt.total_amount = sum((row.import_qty * row.import_price for row in rows), Decimal("0"))
                receipt.save()
                for row in rows:
                    row.receipt = receipt
                    row.conversion_rate = row.item.conversion_rate
                    row.converted_qty = row.import_qty * row.conversion_rate
                    row.save()
                    item = Item.objects.select_for_update().get(pk=row.item_id)
                    item.stock += row.converted_qty
                    item.import_price = row.import_price
                    item.save(update_fields=["stock", "import_price"])
                    TheKho.objects.create(item=item, so_luong=row.converted_qty, ton_cuoi=item.stock, chung_tu=receipt.receipt_code)
            messages.success(request, "Đã nhập kho thành công.")
            return redirect("inventory_receipt", pk=receipt.pk)
    return render(request, "inventory/nhap.html", {"form": form, "formset": formset})

@access
def receipt_detail(request, pk):
    receipt = get_object_or_404(GoodsReceipt.objects.select_related("supplier", "created_by").prefetch_related("details__item"), pk=pk)
    return render(request, "inventory/phieu.html", {"p": receipt})
