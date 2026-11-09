from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import User

# Kiểm tra quyền Quản lý / Admin (BR1: Chỉ Quản lý và Admin mới có quyền quản trị tài khoản)
def is_admin_user(user):
    return user.is_authenticated and (user.is_superuser or user.role in ['QUAN_LY', 'ADMIN'])

# UC_0: Đăng nhập hệ thống
def login_view(request):
    if request.user.is_authenticated:
        return redirect('/management/dashboard/')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # 4a. Thiếu trường bắt buộc
        if not username or not password:
            messages.error(request, "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")
            return render(request, 'accounts/login.html')

        user = User.objects.filter(username=username).first()

        # 5a. Sai tên đăng nhập hoặc mật khẩu
        if user is None or not user.check_password(password):
            messages.error(request, "Tên đăng nhập hoặc mật khẩu không chính xác.")
            return render(request, 'accounts/login.html')

        # 6a. Tài khoản đang ở trạng thái "Đã khóa"
        if not user.is_active:
            reason = f" (Lý do: {user.lock_reason})" if user.lock_reason else ""
            messages.error(request, f"Tài khoản của bạn đã bị khóa{reason}. Vui lòng liên hệ Quản lý.")
            return render(request, 'accounts/login.html')

        # Đăng nhập thành công -> Cấp phiên và chuyển hướng vào Dashboard tổng quan
        login(request, user)
        messages.success(request, f"Xin chào {user.full_name or user.username}!")
        return redirect('/management/dashboard/')

    return render(request, 'accounts/login.html')

# Đăng xuất hệ thống
def logout_view(request):
    # Đăng nhập thành công -> Cấp phiên và chuyển hướng vào Dashboard tổng quan
    login(request, user)
    messages.success(request, f"Xin chào {user.full_name or user.username}!")
    return redirect('dashboard')  # Sửa từ đường dẫn tĩnh thành tên name='dashboard'

# UC_1: Danh sách tài khoản & Quản lý phân quyền (Chỉ Quản lý / Admin)
@login_required(login_url='login')
def user_list_view(request):
    if not is_admin_user(request.user):
        messages.error(request, "Bạn không đủ quyền truy cập")
        return render(request, 'accounts/no_permission.html')

    users = User.objects.all().order_by('-date_joined')

    # Tìm kiếm và lọc
    search_query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_query:
        users = users.filter(Q(username__icontains=search_query) | Q(full_name__icontains=search_query))
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'locked':
        users = users.filter(is_active=False)

    context = {
        'users': users,
        'role_choices': User.ROLE_CHOICES,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
    }
    return render(request, 'accounts/user_list.html', context)

# UC_1.1: Tạo tài khoản mới
@login_required(login_url='login')
def user_create_view(request):
    if not is_admin_user(request.user):
        messages.error(request, "Bạn không đủ quyền truy cập")
        return render(request, 'accounts/no_permission.html')

    creatable_roles = [
        ('QUAN_LY', 'Quản lý (QUAN_LY)'),
        ('THU_KHO', 'Thủ kho (THU_KHO)'),
        ('LE_TAN', 'Lễ tân (LE_TAN)'),
        ('KTV', 'Kỹ thuật viên (KTV)'),
        ('ADMIN', 'Admin (Quản trị viên)'),
    ]

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        password = request.POST.get('password', '').strip()
        role = request.POST.get('role', '').strip()

        if not username or not full_name or not password or not role:
            messages.error(request, "Vui lòng nhập bổ sung đầy đủ các trường bắt buộc.")
            return render(request, 'accounts/user_form.html', {'roles': creatable_roles})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.")
            return render(request, 'accounts/user_form.html', {'roles': creatable_roles})

        new_user = User(
            username=username,
            full_name=full_name,
            role=role,
            is_active=True,
            is_staff=(role == 'ADMIN')
        )
        new_user.set_password(password)
        new_user.save()

        messages.success(request, f"Đã tạo tài khoản '{username}' thành công!")
        return redirect('user_list')

    return render(request, 'accounts/user_form.html', {'roles': creatable_roles})

# UC_1.2: Phân quyền & Khóa tài khoản
@login_required(login_url='login')
def user_detail_view(request, user_id):
    if not is_admin_user(request.user):
        messages.error(request, "Bạn không đủ quyền truy cập")
        return render(request, 'accounts/no_permission.html')

    target_user = User.objects.filter(pk=user_id).first()
    if not target_user:
        messages.error(request, "Tài khoản không còn tồn tại.")
        return redirect('user_list')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_role':
            new_role = request.POST.get('role')
            if new_role in dict(User.ROLE_CHOICES):
                target_user.role = new_role
                target_user.is_staff = (new_role == 'ADMIN')
                target_user.save()
                messages.success(request, f"Đã cập nhật vai trò cho tài khoản '{target_user.username}' thành công.")
                return redirect('user_list')

        elif action == 'lock_account':
            lock_reason = request.POST.get('lock_reason', '').strip()
            if not lock_reason:
                messages.error(request, "Vui lòng nhập lý do khóa tài khoản.")
                return render(request, 'accounts/user_detail.html', {'target_user': target_user, 'roles': User.ROLE_CHOICES})

            target_user.is_active = False
            target_user.lock_reason = lock_reason
            target_user.save()
            messages.warning(request, f"Đã khóa tài khoản '{target_user.username}'.")
            return redirect('user_list')

        elif action == 'unlock_account':
            target_user.is_active = True
            target_user.lock_reason = ""
            target_user.save()
            messages.success(request, f"Đã mở khóa tài khoản '{target_user.username}'.")
            return redirect('user_list')

    return render(request, 'accounts/user_detail.html', {
        'target_user': target_user,
        'roles': User.ROLE_CHOICES,
    })