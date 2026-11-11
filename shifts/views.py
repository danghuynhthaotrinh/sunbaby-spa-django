from datetime import date
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from inventory.models import Item, TheKho
from operations.models import ServiceOrder
from services.models import ServicePackage

from . import services as svc

# ADMIN / QUẢN LÝ / LỄ TÂN / KTV được thao tác điều phối; THỦ KHO chỉ được xem.
OPERATE_ROLES = {"ADMIN", "QUAN_LY", "LE_TAN", "KTV"}
DRAFT_KEY = "uc4_draft"          # thông tin tiếp nhận + gói đã chọn, đi xuyên 5 màn hình


def can_operate(user):
    return user.is_superuser or getattr(user, "role", "") in OPERATE_ROLES


def operator_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_operate(request.user):
            messages.error(request, "Vai trò của bạn chỉ được xem, không được thao tác điều phối ca.")
            return redirect("shifts:dashboard")
        return view(request, *args, **kwargs)
    return wrapper


# ------------------------------------------------------------------ dữ liệu dùng chung
def _rooms():
    return getattr(settings, "SHIFT_ROOMS",
                   ["Body 01", "Body 02", "VIP 01", "Foot 01", "Foot 02",
                    "Thái 01", "Gội 01", "Facial 01"])


def _staff_choices():
    User = get_user_model()
    qs = User.objects.filter(is_active=True, role="KTV").order_by("username")
    return list(qs) if qs.exists() else list(User.objects.filter(is_active=True).order_by("username"))


def _busy():
    serving = ServiceOrder.objects.filter(status=svc.SERVING)
    rooms = set(r for r in serving.values_list("room", flat=True) if r)
    staff = set(serving.exclude(staff=None).values_list("staff_id", flat=True))
    return rooms, staff


def _draft(request):
    return request.session.get(DRAFT_KEY) or {}


def _draft_view(request):
    """Biến nháp trong session thành object đầy đủ; nháp hỏng/gói bị tắt thì xóa."""
    d = _draft(request)
    if not d.get("package"):
        return None
    pkg = (ServicePackage.objects.prefetch_related("bom_items__vat_tu")
           .filter(pk=d["package"], dang_ban=True).first())
    if pkg is None:
        request.session.pop(DRAFT_KEY, None)
        return None
    staff = get_user_model().objects.filter(pk=d.get("staff")).first() if d.get("staff") else None
    return {"pkg": pkg, "staff": staff, "staff_label": svc.staff_label(staff),
            "room": d.get("room", ""), "customer_name": d.get("customer_name", ""),
            "customer_phone": d.get("customer_phone", ""), "note": d.get("note", ""),
            "raw": d}


# ------------------------------------------------------------------ Tab 1: Điều phối ca
@login_required
def dashboard(request):
    try:
        day = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        day = timezone.localdate()
    status = request.GET.get("status", "")
    q = request.GET.get("q", "")
    return render(request, "shifts/dashboard.html", {
        "tab": "dashboard", "day": day, "is_today": day == timezone.localdate(),
        "status": status, "q": q, "status_choices": svc.STATUS_LABELS.items(),
        "counts": svc.day_counts(day), "orders": svc.day_orders(day, status, q),
        "kpi": svc.kpis(), "can_operate": can_operate(request.user),
    })


@operator_required
def new_shift(request):
    """Nút '+ Tạo ca mới': xóa nháp cũ rồi sang bước chọn gói."""
    request.session.pop(DRAFT_KEY, None)
    return redirect("shifts:choose")


# ------------------------------------------------------------------ Tab 2: UC_4.1 Chọn gói dịch vụ
@operator_required
def choose(request):
    pkgs = (ServicePackage.objects.filter(dang_ban=True)
            .prefetch_related("bom_items__vat_tu").order_by("ma_goi"))
    payload = [svc.package_payload(p) for p in pkgs]
    busy_rooms, busy_staff = _busy()
    return render(request, "shifts/choose.html", {
        "tab": "choose", "packages_json": payload, "has_packages": bool(payload),
        "rooms": _rooms(), "busy_rooms": busy_rooms,
        "staff_list": [{"pk": u.pk, "label": svc.staff_label(u), "busy": u.pk in busy_staff}
                       for u in _staff_choices()],
        "draft": _draft(request),
    })


# ------------------------------------------------------------------ Tab 3: UC_4.1.1 Kiểm tra tồn kho
@operator_required
def check(request):
    if request.method == "POST":
        p = request.POST
        draft = {"package": p.get("package", "").strip(), "staff": p.get("staff", "").strip(),
                 "room": p.get("room", "").strip(), "customer_name": p.get("customer_name", "").strip(),
                 "customer_phone": p.get("customer_phone", "").strip(), "note": p.get("note", "").strip()}
        request.session[DRAFT_KEY] = draft
        if not draft["package"]:
            messages.error(request, "Vui lòng chọn gói dịch vụ trước khi kiểm tra tồn kho.")
            return redirect("shifts:choose")
        if not draft["staff"] or not draft["room"]:
            messages.error(request, "Vui lòng chọn KTV đang làm việc và Phòng/Giường.")
            return redirect("shifts:choose")
        return redirect("shifts:check")          # PRG: tải lại bằng GET để F5 không gửi lại form

    dv = _draft_view(request)
    ctx = {"tab": "check", "dv": dv, "items": Item.objects.order_by("sku")}
    if dv is None:
        return render(request, "shifts/check.html", ctx)

    try:                                         # E2: không truy vấn được tồn kho
        chk = svc.check_package(dv["pkg"])
    except Exception:
        ctx["error"] = True
        return render(request, "shifts/check.html", ctx)

    ctx.update({
        "chk": chk,
        "pkg": svc.package_payload(dv["pkg"]) if chk["configured"] else {"name": str(dv["pkg"]), "code": ""},
        "supplies": [r for r in chk["rows"] if not r["is_linen"]],
        "linens": [r for r in chk["rows"] if r["is_linen"]],
        "cost": svc.money(chk.get("cost", 0)),
    })
    return render(request, "shifts/check.html", ctx)


@operator_required
@require_POST
def quick_import(request):
    """UC_4.1.1 A1 – bổ sung vật tư rồi kiểm tra lại."""
    try:
        item = svc.quick_import(item_id=request.POST.get("item"), qty=request.POST.get("qty"),
                                user=request.user)
        messages.success(request, f"Đã nhập nhanh {request.POST.get('qty')} {item.standard_unit} cho "
                                  f"{item}. Hệ thống đã kiểm tra lại tồn kho.")
    except svc.ShiftError as e:
        messages.error(request, str(e))
    back = request.POST.get("back")
    return redirect("shifts:check" if back == "check" else "shifts:choose")


# ------------------------------------------------------------------ Tab 4: UC_4.2 Bắt đầu ca
@login_required
def start(request):
    # --- POST: xác nhận BẮT ĐẦU CA (UC_4.2 + UC_4.2.1)
    if request.method == "POST":
        if not can_operate(request.user):
            messages.error(request, "Vai trò của bạn không được bắt đầu ca.")
            return redirect("shifts:dashboard")
        dv = _draft_view(request)
        if dv is None:
            messages.error(request, "Chưa chọn gói dịch vụ. Hãy chọn gói và kiểm tra tồn kho trước.")
            return redirect("shifts:choose")
        try:
            order = svc.start_shift(
                package_id=dv["pkg"].pk, user=request.user, staff_id=dv["staff"].pk if dv["staff"] else None,
                room=dv["room"], customer_name=dv["customer_name"],
                customer_phone=dv["customer_phone"], note=dv["note"])
        except svc.ShiftError as e:                       # E1: hết hàng ở lần kiểm tra cuối
            messages.error(request, str(e))
            return redirect("shifts:check")
        except Exception:                                 # E3/E2: lỗi hệ thống -> đã rollback
            messages.error(request, "Lỗi hệ thống khi tạo ca hoặc trừ kho. Giao dịch đã được hoàn tác, "
                                    "ca chưa được tạo và tồn kho không đổi.")
            return redirect("shifts:start")
        request.session.pop(DRAFT_KEY, None)
        messages.success(request, f"Đã bắt đầu ca {order.order_code} – kho đã được trừ theo định mức BOM.")
        return redirect(f"{reverse('shifts:start')}?ca={order.pk}")

    ctx = {"tab": "start", "can_operate": can_operate(request.user)}
    ca = request.GET.get("ca", "")
    if ca.isdigit():                                      # xem 1 ca đã tạo
        o = (ServiceOrder.objects.select_related("service", "staff", "detail")
             .filter(pk=ca).first())
        if o is not None:
            ov = svc.order_view(o)
            ctx.update({"mode": "order", "o": ov, "lines": svc.order_lines(o),
                        "cost": svc.money(svc.order_cost(o)),
                        "now_ms": int(timezone.now().timestamp() * 1000)})
            return render(request, "shifts/start.html", ctx)
        messages.error(request, "Không tìm thấy ca yêu cầu.")

    dv = _draft_view(request)                             # chuẩn bị bắt đầu ca mới
    if dv is not None:
        try:
            chk = svc.check_package(dv["pkg"])
        except Exception:                                 # E2: không đọc được tồn kho -> khóa nút
            chk = {"configured": True, "ok": False, "rows": [], "missing": [], "cost": 0,
                   "message": "Không truy vấn được dữ liệu tồn kho. Vui lòng thử lại."}
        ctx.update({"mode": "draft", "dv": dv, "chk": chk,
                    "minutes": int(svc._attr(dv["pkg"], ("thoi_luong_phut",), 0) or 0),
                    "pkg_code": str(svc._attr(dv["pkg"], ("ma_goi",))),
                    "pkg_name": str(svc._attr(dv["pkg"], ("ten",)) or dv["pkg"]),
                    "cost": svc.money(chk.get("cost", 0))})
    else:
        ctx["mode"] = "empty"
    return render(request, "shifts/start.html", ctx)


@operator_required
@require_POST
def complete(request, pk):
    try:
        o = svc.complete_shift(pk, request.user)
        messages.success(request, f"Ca {o.order_code} đã hoàn thành; phòng/KTV được giải phóng, "
                                  f"khăn chuyển sang 'Bẩn chờ giặt'.")
    except ServiceOrder.DoesNotExist:
        messages.error(request, "Không tìm thấy ca.")
        return redirect("shifts:dashboard")
    except svc.ShiftError as e:
        messages.error(request, str(e))
    return redirect(f"{reverse('shifts:start')}?ca={pk}")


@operator_required
@require_POST
def cancel(request, pk):
    try:
        o = svc.cancel_shift(pk, request.user)
        messages.success(request, f"Đã hủy ca {o.order_code} và hoàn trả đúng lượng vật tư/đồ vải về kho.")
    except ServiceOrder.DoesNotExist:
        messages.error(request, "Không tìm thấy ca.")
        return redirect("shifts:dashboard")
    except svc.ShiftError as e:
        messages.error(request, str(e))
    return redirect(f"{reverse('shifts:start')}?ca={pk}")


# ------------------------------------------------------------------ Tab 5: UC_4.2.1 Trừ kho theo BOM
@login_required
def deduct(request):
    ca_code = request.GET.get("ca", "").strip()
    show_all = request.GET.get("all") == "1"

    order = None
    if ca_code:
        order = ServiceOrder.objects.filter(order_code=ca_code).first()
    else:                                                  # mặc định: ca mới nhất hôm nay
        order = (ServiceOrder.objects.filter(started_at__date=timezone.localdate())
                 .order_by("-started_at").first())

    qs = TheKho.objects.select_related("item").order_by("-ngay", "-id")
    if not show_all:
        qs = qs.filter(Q(loai_bien_dong__startswith=svc.LOAI_OUT) |
                       Q(loai_bien_dong__startswith=svc.LOAI_REFUND) |
                       Q(loai_bien_dong__startswith=svc.LOAI_QUICK))
    if ca_code:
        qs = qs.filter(chung_tu=ca_code)
    item_id = request.GET.get("item", "")
    if item_id.isdigit():
        qs = qs.filter(item_id=item_id)

    ctx = {"tab": "deduct", "rows": svc.movement_rows(qs[:300]), "ca_code": ca_code,
           "show_all": show_all, "item_id": item_id, "items": Item.objects.order_by("sku"),
           "recent_orders": ServiceOrder.objects.order_by("-started_at")[:40],
           "order": None}
    if order is not None:
        lines = svc.order_lines(order)
        refunded = order.status == svc.CANCELLED
        ctx.update({"order": svc.order_view(order), "n_supply": sum(1 for l in lines if not l["is_linen"]),
                    "n_linen": sum(1 for l in lines if l["is_linen"]), "refunded": refunded,
                    "cost": svc.money(0 if refunded else svc.order_cost(order))})
    return render(request, "shifts/deduct.html", ctx)


@operator_required
@require_POST
def reset_demo(request):
    if not request.user.is_superuser:
        messages.error(request, "Chỉ Admin (superuser) mới được reset dữ liệu demo.")
    else:
        svc.reset_demo()
        request.session.pop(DRAFT_KEY, None)
        messages.success(request, "Đã hoàn kho các ca đang chạy và xóa danh sách ca demo.")
    return redirect("shifts:dashboard")
