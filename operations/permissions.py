from django.core.exceptions import PermissionDenied


def require_user(user, management=False):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied('Vui lòng đăng nhập bằng tài khoản đang hoạt động.')
    if management and not (user.is_superuser or user.role in ['ADMIN', 'QUAN_LY', 'THU_KHO', 'MANAGER']):
        raise PermissionDenied('Chức năng dành cho Quản lý/Thủ kho và Admin.')
