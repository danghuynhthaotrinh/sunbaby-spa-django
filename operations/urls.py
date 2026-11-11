from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path('dang-nhap/', LoginView.as_view(template_name='operations/login.html', redirect_authenticated_user=True, next_page='operations_home'), name='operations_login'),
    path('dang-xuat/', LogoutView.as_view(next_page='operations_login'), name='operations_logout'),
    path('', views.operations_home, name='operations_home'),
    path('phieu/<int:pk>/', views.shipment_detail, name='operations_shipment_detail'),
]
