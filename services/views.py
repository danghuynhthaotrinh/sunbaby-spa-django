from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventory.models import Item
from .forms import BOMFormSet, DonGiaVonForm, ServicePackageForm
from .models import ServicePackage


def vnd(x):
    return f"{x:,.0f}".replace(",", ".") + "đ"


def la_quan_ly(user):
    # TODO: sửa theo cách UC_0 của nhóm bạn phân vai trò
    return user.is_superuser or user.groups.filter(name="Quản lý").exists()


def quan_ly_required(view):                       # BR1: chỉ Quản lý
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not la_quan_ly(request.user):
            raise PermissionDenied("Bạn không có quyền thực hiện chức năng này.")
        return view(request, *args, **kwargs)
    return wrapper


def _goi_qs():
    return ServicePackage.objects.prefetch_related("bom_items__vat_tu")


# ---------- UC_3: màn hình tổng quan ----------
@quan_ly_required
def home(request):
    return render(request, "services/home.html")


# ---------- UC_3.1: Quản lý gói dịch vụ ----------
@quan_ly_required
def package_list(request):
    qs = ServicePackage.objects.all()
    q = request.GET.get("q", "").strip()
    tt = request.GET.get("tt", "")
    if q:                                                   # A3
        qs = qs.filter(Q(ma_goi__icontains=q) | Q(ten__icontains=q))
    if tt == "dang_ban":
        qs = qs.filter(dang_ban=True)
    elif tt == "ngung":
        qs = qs.filter(dang_ban=False)
    page = Paginator(qs, 10).get_page(request.GET.get("page"))
    return render(request, "services/package_list.html",
                  {"page": page, "q": q, "tt": tt, "tab": "goi"})


@quan_ly_required
def package_save(request, pk=None):               # thêm mới (pk=None) hoặc sửa (A1)
    goi = get_object_or_404(ServicePackage, pk=pk) if pk else None
    form = ServicePackageForm(request.POST or None, instance=goi)
    if request.method == "POST" and form.is_valid():
        goi = form.save()
        messages.success(request, f"Đã lưu gói dịch vụ {goi.ma_goi}.")
        return redirect("services:package_list")
    return render(request, "services/package_form.html",
                  {"form": form, "goi": goi, "tab": "goi"})


@quan_ly_required
@require_POST
def package_toggle(request, pk):                  # A2: ngừng / kích hoạt
    goi = get_object_or_404(ServicePackage, pk=pk)
    goi.dang_ban = not goi.dang_ban
    goi.save(update_fields=["dang_ban"])
    trang_thai = "kích hoạt" if goi.dang_ban else "ngừng hoạt động"
    messages.success(request, f"Đã {trang_thai} gói {goi.ma_goi}.")
    return redirect("services:package_list")


# ---------- UC_3.2: Cấu hình BOM ----------
@quan_ly_required
def bom_config(request, pk):
    goi = get_object_or_404(_goi_qs(), pk=pk)
    formset = BOMFormSet(request.POST or None, instance=goi)
    if request.method == "POST" and formset.is_valid():
        with transaction.atomic():
            formset.save()
        goi = _goi_qs().get(pk=pk)                # tính lại giá vốn (UC_3.2.1)
        messages.success(request,
                         f"Đã lưu BOM. Giá vốn mới: {vnd(goi.chi_phi_nguyen_vat)}")
        return redirect("services:bom_config", pk=pk)
    return render(request, "services/bom_config.html",
                  {"goi": goi, "formset": formset, "tab": "goi"})


# ---------- UC_3.2.1: Giá vốn lý thuyết ----------
@quan_ly_required
def cost_list(request):
    form = DonGiaVonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():          # A2
        vt = form.cleaned_data["vat_tu"]
        if not vt.conversion_rate:
            form.add_error("vat_tu", "Vật tư chưa có tỷ lệ quy đổi.")
        else:
            vt.import_price = form.cleaned_data["don_gia_von"] * vt.conversion_rate
            vt.save(update_fields=["import_price"])
            messages.success(request, f"Đã cập nhật đơn giá vốn của {vt}. "
                                      "Giá vốn các gói liên quan đã được tính lại.")
            return redirect("services:cost_list")

    vat_tu_rows = [
        {"obj": v,
         "gia_von": (v.import_price / v.conversion_rate)
                    if v.conversion_rate and v.import_price is not None else None}
        for v in Item.objects.all()
    ]
    return render(request, "services/cost_list.html", {
        "goi_list": _goi_qs(), "form": form,
        "vat_tu_rows": vat_tu_rows, "tab": "cost",
    })


@quan_ly_required
def cost_detail(request, pk):                     # A1: xem chi tiết một gói
    goi = get_object_or_404(_goi_qs(), pk=pk)
    return render(request, "services/cost_detail.html",
                  {"goi": goi, "dong_list": goi.bom_items.all(), "tab": "cost"})