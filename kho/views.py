# -*- coding: utf-8 -*-
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from inventory.models import Item, Supplier, GoodsReceipt, GoodsReceiptDetail
from .forms import ItemForm, SupplierForm, ReceiptForm, ReceiptDetailFormSet
from .models import TheKho
from .models import CATEGORIES

def access(view):
 @login_required
 def wrapped(request,*args,**kwargs):
  if getattr(request.user,"role","") not in ("MANAGER","ADMIN"): raise PermissionDenied
  return view(request,*args,**kwargs)
 return wrapped

@access
def index(request):
 qs=Item.objects.select_related("supplier").all()
 q=request.GET.get("q","")
 if q: qs=qs.filter(Q(sku__icontains=q)|Q(name__icontains=q))
 if request.GET.get("nhom"): qs=qs.filter(category=request.GET["nhom"])
 if request.GET.get("ncc"): qs=qs.filter(supplier_id=request.GET["ncc"])
 today=timezone.localdate()
 idle=[]
 for item in Item.objects.filter(stock__gt=0):
  last=item.the_kho.filter(loai_bien_dong__icontains="xuất").order_by("-ngay").first()
  receipt=GoodsReceiptDetail.objects.filter(item=item).order_by("-receipt__created_at").first()
  date=last.ngay.date() if last else (receipt.receipt.created_at.date() if receipt else today)
  if (today-date).days>=45: idle.append((item,(today-date).days))
 return render(request,"kho/index_v2.html",{"items":Paginator(qs.order_by("sku"),15).get_page(request.GET.get("page")),"q":q,"nhoms":CATEGORIES.items(),"nccs":Supplier.objects.all(),"n_vattu":Item.objects.count(),"n_ncc":Supplier.objects.count(),"low":Item.objects.filter(stock__lt=F("min_stock")).count(),"phieus":GoodsReceipt.objects.select_related("supplier","created_by").order_by("-created_at"),"canh_bao":idle,"lo_han":GoodsReceiptDetail.objects.filter(expiry_date__range=(today,today+timedelta(days=30))).select_related("item")})

@access
def vat_tu_form(request,pk=None):
 obj=get_object_or_404(Item,pk=pk) if pk else None
 form=ItemForm(request.POST or None,instance=obj)
 if form.is_valid(): form.save(); messages.success(request,"Đã lưu vật tư."); return redirect("kho:index")
 return render(request,"kho/form.html",{"form":form,"title":"Cập nhật vật tư" if obj else "Thêm vật tư"})

@access
def vat_tu_delete(request,pk):
 obj=get_object_or_404(Item,pk=pk)
 if request.method=="POST": obj.delete(); messages.success(request,"Đã xóa vật tư."); return redirect("kho:index")
 return render(request,"kho/delete.html",{"obj":obj})

@access
def ncc_form(request):
 form=SupplierForm(request.POST or None)
 if form.is_valid(): form.save(); messages.success(request,"Đã lưu nhà cung cấp."); return redirect("kho:index")
 return render(request,"kho/form.html",{"form":form,"title":"Nhà cung cấp"})

@access
def nhap_kho(request):
 form=ReceiptForm(request.POST or None)
 instance=GoodsReceipt()
 fs=ReceiptDetailFormSet(request.POST or None,instance=instance)
 if request.method=="POST" and form.is_valid() and fs.is_valid():
  rows=[d for d in fs.save(commit=False) if d.item_id and d.import_qty]
  if not rows: messages.error(request,"Phiếu nhập cần có ít nhất một dòng hàng.")
  elif any(d.import_qty<=0 or d.import_price<0 or d.item.conversion_rate<=0 for d in rows): messages.error(request,"Số lượng phải dương, đơn giá không âm và tỷ lệ quy đổi phải dương.")
  else:
   with transaction.atomic():
    receipt=form.save(commit=False); receipt.created_by=request.user
    prefix=f"PN-{timezone.localdate():%Y%m%d}-"
    last=GoodsReceipt.objects.select_for_update().filter(receipt_code__startswith=prefix).order_by("-receipt_code").first()
    receipt.receipt_code=f"{prefix}{int(last.receipt_code[-3:])+1 if last else 1:03d}"
    receipt.total_amount=sum((d.import_qty*d.import_price for d in rows),start=0)
    receipt.save()
    for d in rows:
     d.receipt=receipt; d.conversion_rate=d.item.conversion_rate
     d.converted_qty=d.import_qty*d.conversion_rate
     d.save()
     item=Item.objects.select_for_update().get(pk=d.item_id)
     item.stock+=d.converted_qty; item.import_price=d.import_price
     item.save(update_fields=["stock","import_price"])
     TheKho.objects.create(item=item,so_luong=d.converted_qty,ton_cuoi=item.stock,chung_tu=receipt.receipt_code)
   return redirect("kho:phieu",pk=receipt.pk)
 return render(request,"kho/nhap.html",{"form":form,"formset":fs})

@access
def phieu_detail(request,pk):
 return render(request,"kho/phieu.html",{"p":get_object_or_404(GoodsReceipt.objects.select_related("supplier","created_by").prefetch_related("details__item"),pk=pk)})
