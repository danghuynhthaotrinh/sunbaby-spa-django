"""Nghiệp vụ UC_4 – Điều phối ca (không chứa code giao diện).

UC_4.1    package_payload()  - thông tin gói + BOM cho màn hình chọn gói
UC_4.1.1  check_package()    - kiểm tra tồn kho theo BOM (CHỈ ĐỌC)
UC_4.2    start_shift()      - tạo ca trong 1 transaction
UC_4.2.1  (trong start_shift) - trừ vật tư, đổi trạng thái đồ vải, ghi thẻ kho, sinh phiếu xuất
UC_4 A1   complete_shift()   - hoàn thành ca: khăn Đang phục vụ -> Bẩn
UC_4 A2   cancel_shift()     - hủy ca, hoàn kho đúng lượng đã trừ
"""
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from inventory.models import Item, TheKho
from operations.models import LinenTracking, ServiceOrder
from services.models import BOMItem, ServicePackage

from .models import ServiceOrderDetail, ServiceOrderLine

SERVING, COMPLETED, CANCELLED = "SERVING", "COMPLETED", "CANCELLED"
STATUS_LABELS = {
    SERVING: "Đang phục vụ",
    COMPLETED: "Đã hoàn thành",
    CANCELLED: "Đã hủy & Hoàn kho",
}
LOAI_OUT = "Trừ kho ca dịch vụ"
LOAI_REFUND = "Hoàn trả hủy ca"
LOAI_QUICK = "Nhập kho nhanh"
SHIFT_LOAI = (LOAI_OUT, LOAI_REFUND, LOAI_QUICK)


class ShiftError(Exception):
    """Lỗi nghiệp vụ - thông báo thẳng cho người dùng."""


# ------------------------------------------------------------------ helpers
def fmt(d):
    """Decimal -> chuỗi gọn (bỏ số 0 thừa)."""
    d = Decimal(str(d))
    s = format(d.normalize(), "f")
    return s


def money(d):
    """12345.6 -> '12.346đ'."""
    try:
        n = int(Decimal(str(d or 0)).to_integral_value())
    except Exception:
        n = 0
    return f"{n:,}".replace(",", ".") + "đ"


def _attr(obj, names, default=""):
    """Lấy field đầu tiên tồn tại (để chịu được khác biệt tên field giữa các nhóm)."""
    for n in names:
        v = getattr(obj, n, None)
        if v not in (None, ""):
            return v
    return default


def _unit(item):
    return getattr(item, "standard_unit", "") or ""


def _name(item):
    return getattr(item, "name", None) or str(item)


def _int_ceil(d):
    return int(Decimal(str(d)).to_integral_value(rounding=ROUND_CEILING))


def staff_label(user):
    if user is None:
        return "—"
    full = (getattr(user, "full_name", "") or "").strip()
    return f"{user.username} {full}".strip() if full else user.username


def unit_cost(item):
    """Giá vốn 1 đơn vị chuẩn = giá nhập / tỷ lệ quy đổi."""
    price = Decimal(str(item.import_price or 0))
    rate = Decimal(str(item.conversion_rate or 1))
    return price / rate if rate else price


# ------------------------------------------------------------------ UC_4.1.1
def check_package(package, lock=False):
    """Đối chiếu từng dòng BOM với tồn kho thực tế. Không thay đổi dữ liệu.

    Vật tư tiêu hao : so với Item.stock
    Đồ vải          : so với LinenTracking.clean_qty (đồ vải SẠCH)
    """
    bom = list(package.bom_items.all())
    if not bom:
        return {"configured": False, "ok": False, "rows": [], "missing": [],
                "message": "Gói chưa cấu hình BOM nên chưa thể bắt đầu ca."}

    ids = [b.vat_tu_id for b in bom]
    item_qs = Item.objects.filter(pk__in=ids)
    if lock:
        item_qs = item_qs.select_for_update()
    items = {i.pk: i for i in item_qs}

    linen_ids = [i.pk for i in items.values() if i.is_linen]
    lin_qs = LinenTracking.objects.filter(item_id__in=linen_ids)
    if lock:
        lin_qs = lin_qs.select_for_update()
    trackings = {t.item_id: t for t in lin_qs}

    rows, missing = [], []
    for b in bom:
        item = items[b.vat_tu_id]
        tracking = trackings.get(item.pk)
        raw_need = Decimal(str(b.dinh_luong))
        if item.is_linen:
            have = Decimal(tracking.clean_qty) if tracking else Decimal(str(item.stock or 0))
            need = Decimal(_int_ceil(raw_need))
        else:
            have = Decimal(str(item.stock or 0))
            need = raw_need
        enough = have >= need
        if not enough:
            missing.append(_name(item))
        mn = Decimal(str(item.min_stock or 0))
        after = have - need
        rows.append({
            "item": item, "sku": item.sku, "name": _name(item), "unit": _unit(item),
            "need": need, "have": have, "after": after, "min": mn,
            "short": max(need - have, Decimal("0")),
            "enough": enough, "low_after": enough and after < mn,
            "is_linen": item.is_linen, "tracking": tracking,
            "cost": Decimal("0") if item.is_linen else need * unit_cost(item),
        })

    ok = not missing
    message = ("Đủ vật tư & Đồ vải sạch để phục vụ ca" if ok else
               "Không thể bắt đầu ca! Vật tư [" + ", ".join(missing) +
               "] trong kho không đủ định mức. Vui lòng bổ sung hoặc liên hệ Thủ kho!")
    return {"configured": True, "ok": ok, "rows": rows, "missing": missing,
            "message": message, "cost": sum((r["cost"] for r in rows), Decimal("0")),
            "low": [r["name"] for r in rows if r["low_after"]]}


def package_payload(package):
    """Dữ liệu 1 gói (kèm BOM + kết quả kiểm tra) để đổ vào màn hình UC_4.1 dạng JSON."""
    chk = check_package(package)
    return {
        "id": package.pk,
        "code": str(_attr(package, ("ma_goi",))),
        "name": str(_attr(package, ("ten",)) or package),
        "group": str(_attr(package, ("nhom_dich_vu", "nhom", "loai", "danh_muc"), "—")),
        "minutes": int(_attr(package, ("thoi_luong_phut",), 0) or 0),
        "price": money(_attr(package, ("gia_ban",), 0)),
        "staff": str(_attr(package, ("so_nhan_su", "so_ktv"), 1)),
        "cost": money(chk.get("cost", 0)),
        "configured": chk["configured"], "ok": chk["ok"], "missing": chk["missing"],
        "rows": [{"sku": r["sku"], "name": r["name"], "unit": r["unit"], "need": fmt(r["need"]),
                  "have": fmt(r["have"]), "enough": r["enough"], "linen": r["is_linen"]}
                 for r in chk["rows"]],
    }


# ------------------------------------------------------------------ nội bộ
def _next_order_code():
    prefix = f"CA-{timezone.localtime():%y%m%d}-"
    last = (ServiceOrder.objects.filter(order_code__startswith=prefix)
            .order_by("-order_code").first())
    n = int(last.order_code.rsplit("-", 1)[-1]) + 1 if last else 1
    return f"{prefix}{n:03d}"


def _get_tracking(item, lock=True):
    qs = LinenTracking.objects.select_for_update() if lock else LinenTracking.objects
    t = qs.filter(item=item).first()
    if t is None:
        t = LinenTracking.objects.create(item=item, clean_qty=max(int(item.stock or 0), 0))
    return t


def _card(item, mtype, qty, balance, voucher):
    """Ghi 1 dòng vào inventory.TheKho (thẻ kho chung của cả hệ thống)."""
    TheKho.objects.create(item=item, loai_bien_dong=mtype, so_luong=qty,
                          ton_cuoi=balance, chung_tu=voucher)


# ------------------------------------------------------------------ UC_4.2 / 4.2.1
def start_shift(*, package_id, user, staff_id=None, room="", customer_name="",
                customer_phone="", note=""):
    try:
        package_id = int(package_id)
    except (TypeError, ValueError):
        raise ShiftError("Chưa chọn gói dịch vụ.")

    room = (room or "").strip()
    staff = None
    if staff_id:
        staff = get_user_model().objects.filter(pk=staff_id, is_active=True).first()
        if staff is None:
            raise ShiftError("Kỹ thuật viên không hợp lệ.")

    with transaction.atomic():
        try:
            package = (ServicePackage.objects.select_for_update()
                       .prefetch_related("bom_items").get(pk=package_id, dang_ban=True))
        except ServicePackage.DoesNotExist:
            raise ShiftError("Gói dịch vụ không tồn tại hoặc đã ngừng hoạt động.")

        serving = ServiceOrder.objects.filter(status=SERVING)
        if room and serving.filter(room=room).exists():
            raise ShiftError(f"{room} đang có ca phục vụ, vui lòng chọn phòng khác.")
        if staff and serving.filter(staff=staff).exists():
            raise ShiftError("KTV này đang phục vụ một ca khác.")

        chk = check_package(package, lock=True)          # kiểm tra lại lần cuối (UC_4.2 bước 3)
        if not chk["configured"] or not chk["ok"]:
            raise ShiftError(chk["message"])

        code = _next_order_code()
        order = ServiceOrder.objects.create(
            order_code=code, service=package, staff=staff, room=room or None,
            status=SERVING)                               # started_at tự ghi (auto_now_add)
        ServiceOrderDetail.objects.create(
            order=order, issue_code=f"PXK-{code}", created_by=user,
            customer_name=(customer_name or "").strip(),
            customer_phone=(customer_phone or "").strip(),
            note=(note or "").strip())

        for r in chk["rows"]:                             # UC_4.2.1
            item, need = r["item"], r["need"]
            if r["is_linen"]:                              # Kho sạch -> Đang phục vụ
                t = r["tracking"] or _get_tracking(item)
                q = int(need)
                t.clean_qty -= q
                t.in_service_qty += q
                t.save(update_fields=["clean_qty", "in_service_qty"])
                ServiceOrderLine.objects.create(order=order, item=item, quantity=q, is_linen=True)
                _card(item, LOAI_OUT, -q, t.clean_qty, code)
            else:                                          # Trừ vật tư tiêu hao
                item.stock = Decimal(str(item.stock)) - need
                if item.stock < 0:
                    raise ShiftError(f"Tồn kho {_name(item)} không được âm.")
                item.save(update_fields=["stock"])
                ServiceOrderLine.objects.create(order=order, item=item, quantity=need, is_linen=False)
                _card(item, LOAI_OUT, -need, item.stock, code)
    return order


# ------------------------------------------------------------------ A1: hoàn thành
def complete_shift(order_id, user=None):
    with transaction.atomic():
        order = ServiceOrder.objects.select_for_update().get(pk=order_id)
        if order.status != SERVING:
            raise ShiftError("Chỉ ca đang phục vụ mới được hoàn thành.")
        for line in order.shift_lines.select_related("item").filter(is_linen=True):
            t = _get_tracking(line.item)
            q = int(line.quantity)
            t.in_service_qty = max(t.in_service_qty - q, 0)
            t.dirty_qty += q                               # Đang phục vụ -> Bẩn
            t.save(update_fields=["in_service_qty", "dirty_qty"])
        order.status = COMPLETED
        order.completed_at = timezone.now()
        order.save(update_fields=["status", "completed_at"])
    return order


# ------------------------------------------------------------------ A2: hủy + hoàn kho
def _refund(order, user):
    for line in order.shift_lines.select_related("item"):
        item = Item.objects.select_for_update().get(pk=line.item_id)
        if line.is_linen:
            t = _get_tracking(item)
            q = int(line.quantity)
            t.in_service_qty = max(t.in_service_qty - q, 0)
            t.clean_qty += q                               # Đang phục vụ -> Sạch
            t.save(update_fields=["in_service_qty", "clean_qty"])
            _card(item, LOAI_REFUND, q, t.clean_qty, order.order_code)
        else:
            item.stock = Decimal(str(item.stock)) + line.quantity
            item.save(update_fields=["stock"])
            _card(item, LOAI_REFUND, line.quantity, item.stock, order.order_code)


def cancel_shift(order_id, user=None):
    with transaction.atomic():
        order = ServiceOrder.objects.select_for_update().get(pk=order_id)
        if order.status != SERVING:
            raise ShiftError("Chỉ ca đang phục vụ mới được hủy.")
        _refund(order, user)
        order.status = CANCELLED
        order.completed_at = timezone.now()
        order.save(update_fields=["status", "completed_at"])
    return order


# ------------------------------------------------------------------ + Nhập kho nhanh (UC_4.1.1 A1)
def quick_import(*, item_id, qty, user):
    try:
        qty = Decimal(str(qty).replace(",", "."))
    except Exception:
        raise ShiftError("Số lượng không hợp lệ.")
    if qty <= 0:
        raise ShiftError("Số lượng nhập phải lớn hơn 0.")
    with transaction.atomic():
        try:
            item = Item.objects.select_for_update().get(pk=item_id)
        except (Item.DoesNotExist, ValueError, TypeError):
            raise ShiftError("Vui lòng chọn vật tư (SKU).")
        if item.is_linen:
            t = _get_tracking(item)
            t.clean_qty += _int_ceil(qty)
            t.save(update_fields=["clean_qty"])
            balance = t.clean_qty
        else:
            item.stock = Decimal(str(item.stock)) + qty
            item.save(update_fields=["stock"])
            balance = item.stock
        _card(item, LOAI_QUICK, qty, balance, f"NN-{timezone.localtime():%y%m%d%H%M%S}")
    return item


# ------------------------------------------------------------------ Reset demo
def reset_demo():
    with transaction.atomic():
        for o in ServiceOrder.objects.select_for_update().filter(status=SERVING):
            _refund(o, None)
        ServiceOrder.objects.all().delete()      # thẻ kho được giữ lại làm lịch sử


# ------------------------------------------------------------------ dữ liệu cho giao diện
def _detail(o):
    try:
        return o.detail
    except ServiceOrderDetail.DoesNotExist:
        return None


def order_view(o):
    """Gói 1 ca thành dict thân thiện cho template."""
    d = _detail(o)
    pkg = o.service
    minutes = int(_attr(pkg, ("thoi_luong_phut",), 0) or 0)
    start = timezone.localtime(o.started_at)
    end_real = timezone.localtime(o.completed_at) if o.completed_at else None
    expected_end = start + timedelta(minutes=minutes)
    return {
        "obj": o, "pk": o.pk, "code": o.order_code, "status": o.status,
        "status_label": STATUS_LABELS.get(o.status, o.status),
        "package_code": str(_attr(pkg, ("ma_goi",))), "package_name": str(_attr(pkg, ("ten",)) or pkg),
        "minutes": minutes, "staff": staff_label(o.staff), "room": o.room or "—",
        "customer": (d.customer_name if d and d.customer_name else ""),
        "phone": (d.customer_phone if d else ""),
        "note": (d.note if d else ""), "issue_code": (d.issue_code if d else ""),
        "start": start, "end_real": end_real, "expected_end": expected_end,
        "end_text": (f"{start:%H:%M}–{end_real:%H:%M}" if end_real
                     else f"{start:%H:%M}–{expected_end:%H:%M}"),
        "started_ms": int(o.started_at.timestamp() * 1000),
    }


def order_lines(order):
    out = []
    for ln in order.shift_lines.select_related("item").order_by("is_linen", "id"):
        out.append({"sku": ln.item.sku, "name": _name(ln.item), "unit": _unit(ln.item),
                    "qty": fmt(ln.quantity), "is_linen": ln.is_linen,
                    "cost": Decimal("0") if ln.is_linen else ln.quantity * unit_cost(ln.item)})
    return out


def order_cost(order):
    return sum((l["cost"] for l in order_lines(order)), Decimal("0"))


def day_orders(day, status="", q=""):
    qs = ServiceOrder.objects.filter(started_at__date=day).select_related("service", "staff", "detail")
    if status in STATUS_LABELS:
        qs = qs.filter(status=status)
    q = (q or "").strip()
    if q:
        qs = qs.filter(Q(order_code__icontains=q) | Q(detail__customer_name__icontains=q)
                       | Q(detail__customer_phone__icontains=q))
    return [order_view(o) for o in qs.order_by("-started_at")]


def day_counts(day):
    qs = ServiceOrder.objects.filter(started_at__date=day)
    return {"total": qs.count(), "serving": qs.filter(status=SERVING).count(),
            "completed": qs.filter(status=COMPLETED).count(),
            "cancelled": qs.filter(status=CANCELLED).count()}


def movement_rows(qs):
    """Chuyển các dòng TheKho thành dữ liệu hiển thị cho màn hình UC_4.2.1."""
    rows = []
    for c in qs:
        loai = c.loai_bien_dong or ""
        linen = bool(c.item.is_linen)
        if loai.startswith(LOAI_OUT):
            kind, note = "out", ("Chuyển từ Sạch sang Đang dùng" if linen else "Tiêu hao trực tiếp")
        elif loai.startswith(LOAI_REFUND):
            kind, note = "refund", ("Trả về Tủ Khăn Sạch" if linen else "Hoàn trả vật tư về kho")
        elif loai.startswith(LOAI_QUICK):
            kind, note = "quick", "Bổ sung nhanh từ màn hình điều phối"
        else:
            kind, note = "other", ""
        qty = Decimal(str(c.so_luong))
        rows.append({
            "code": f"TK-{c.pk:03d}", "sku": c.item.sku, "name": _name(c.item),
            "loai": LOAI_OUT if kind == "out" else (LOAI_REFUND if kind == "refund" else loai),
            "kind": kind, "qty": ("+" if qty > 0 else "") + fmt(qty), "unit": _unit(c.item),
            "positive": qty > 0, "balance": fmt(c.ton_cuoi), "voucher": c.chung_tu,
            "when": timezone.localtime(c.ngay), "note": note,
        })
    return rows


def kpis():
    """Thanh KPI vận hành (UC_4 bước 1): công suất, ca đang chạy, tồn kho chính, khăn bẩn."""
    today = timezone.localdate()
    cap = getattr(settings, "SHIFT_DAILY_CAPACITY", 70)
    todays = ServiceOrder.objects.filter(started_at__date=today)
    served = todays.exclude(status=CANCELLED).count()
    serving = ServiceOrder.objects.filter(status=SERVING).count()

    used_ids = BOMItem.objects.filter(goi__dang_ban=True).values_list("vat_tu_id", flat=True)
    tracks = {t.item_id: t for t in LinenTracking.objects.all()}
    stock_cards = []
    for it in Item.objects.filter(pk__in=set(used_ids)):
        have = Decimal(tracks[it.pk].clean_qty) if (it.is_linen and it.pk in tracks) else Decimal(str(it.stock or 0))
        mn = Decimal(str(it.min_stock or 0))
        stock_cards.append({"name": _name(it), "unit": _unit(it), "have": have, "min": mn,
                            "low": have <= mn, "ratio": (have / mn) if mn else Decimal("999999")})
    stock_cards.sort(key=lambda x: x["ratio"])
    dirty = LinenTracking.objects.aggregate(s=Sum("dirty_qty"))["s"] or 0
    return {"served": served, "capacity": cap,
            "percent": min(int(served * 100 / cap), 100) if cap else 0,
            "serving": serving, "stock_cards": stock_cards[:3], "dirty": dirty}
