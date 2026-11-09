# -*- coding: utf-8 -*-
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import VatTuForm, NhaCungCapForm, PhieuForm, DongFormSet
from .models import VatTu, NhaCungCap, NhomVatTu, PhieuNhap, DongPhieuNhap, TheKho


def co_quyen(user):
    return user.is_authenticated and (getattr(user, "role", "") == "MANAGER" or user.groups.filter(name__in=["Quản lý", "Thủ kho"]).exists())


def quyen(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not co_quyen(request.user):
            messages.error(request, "Bạn không có quyền truy cập chức năng kho.")
            return redirect("kho:index")
        return view(request, *args, **kwargs)
    return wrapped


@quyen
def index(request):
    vat_tus = VatTu.objects.select_related("nhom", "ncc_mac_dinh").all()
    q = request.GET.get("q", "")
    if q:
        vat_tus = vat_tus.filter(Q(sku__icontains=q) | Q(ten__icontains=q))
    if request.GET.get("nhom"):
        vat_tus = vat_tus.filter(nhom_id=request.GET["nhom"])
    if request.GET.get("ncc"):
        vat_tus = vat_tus.filter(ncc_mac_dinh_id=request.GET["ncc"])
    hom_nay = timezone.localdate()
    canh_bao = []
    for vat_tu in VatTu.objects.filter(ton_kha_dung__gt=0):
        xuat = vat_tu.the_kho.filter(loai_bien_dong__icontains="xuất").order_by("-ngay").first()
        nhap = vat_tu.the_kho.filter(loai_bien_dong__icontains="nhập").order_by("-ngay").first()
        moc = xuat.ngay.date() if xuat else (nhap.ngay.date() if nhap else hom_nay)
        if (hom_nay - moc).days >= 45:
            canh_bao.append((vat_tu, (hom_nay - moc).days))
    return render(request, "kho/index_v2.html", {"items": Paginator(vat_tus.order_by("sku"), 12).get_page(request.GET.get("page")), "q": q, "nhoms": NhomVatTu.objects.all(), "nccs": NhaCungCap.objects.all(), "n_vattu": VatTu.objects.count(), "n_ncc": NhaCungCap.objects.count(), "low": VatTu.objects.filter(ton_kha_dung__lt=F("ton_toi_thieu")).count(), "phieus": PhieuNhap.objects.select_related("ncc", "nguoi_nhap").order_by("-ngay_nhap"), "canh_bao": canh_bao, "lo_han": DongPhieuNhap.objects.filter(han_su_dung__range=(hom_nay, hom_nay + timedelta(days=30)))})


@quyen
def vat_tu_form(request, pk=None):
    instance = get_object_or_404(VatTu, pk=pk) if pk else None
    form = VatTuForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save(); messages.success(request, "Đã lưu vật tư."); return redirect("kho:index")
    return render(request, "kho/form.html", {"form": form, "title": "Cập nhật vật tư" if instance else "Thêm vật tư"})


@quyen
def vat_tu_delete(request, pk):
    item = get_object_or_404(VatTu, pk=pk)
    if request.method == "POST":
        item.delete(); messages.success(request, "Đã xóa vật tư."); return redirect("kho:index")
    return render(request, "kho/delete.html", {"obj": item})


@quyen
def ncc_form(request):
    form = NhaCungCapForm(request.POST or None)
    if form.is_valid():
        form.save(); messages.success(request, "Đã thêm nhà cung cấp."); return redirect("kho:index")
    return render(request, "kho/form.html", {"form": form, "title": "Thêm nhà cung cấp"})


@quyen
def nhap_kho(request):
    phieu_moi = PhieuNhap()
    form = PhieuForm(request.POST or None)
    formset = DongFormSet(request.POST or None, instance=phieu_moi)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        dong_hang = [dong for dong in formset.save(commit=False) if dong.vat_tu_id and dong.so_luong_nhap]
        if not dong_hang:
            messages.error(request, "Phiếu nhập cần có ít nhất một dòng hàng.")
        elif any(d.so_luong_nhap <= 0 or d.don_gia_mua < 0 or d.vat_tu.ty_le_quy_doi <= 0 for d in dong_hang):
            messages.error(request, "Số lượng phải dương, đơn giá không âm và tỷ lệ quy đổi phải dương.")
        else:
            with transaction.atomic():
                phieu = form.save(commit=False); phieu.nguoi_nhap = request.user; phieu.save()
                for dong in dong_hang:
                    dong.phieu = phieu; dong.save()
                    vat_tu = VatTu.objects.select_for_update().get(pk=dong.vat_tu_id)
                    vat_tu.ton_kha_dung += dong.so_luong_quy_doi; vat_tu.don_gia_nhap = dong.don_gia_mua
                    vat_tu.save(update_fields=["ton_kha_dung", "don_gia_nhap"])
                    TheKho.objects.create(vat_tu=vat_tu, so_luong=dong.so_luong_quy_doi, ton_cuoi=vat_tu.ton_kha_dung, chung_tu=phieu.ma_phieu)
            messages.success(request, "Đã nhập kho thành công."); return redirect("kho:phieu", pk=phieu.pk)
    return render(request, "kho/nhap.html", {"form": form, "formset": formset})


@quyen
def phieu_detail(request, pk):
    return render(request, "kho/phieu.html", {"p": get_object_or_404(PhieuNhap.objects.select_related("ncc", "nguoi_nhap").prefetch_related("dong_hang__vat_tu"), pk=pk)})
