from django.urls import path

from . import views

app_name = "shifts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),                         # Tab 1: Điều phối ca
    path("tao-ca-moi/", views.new_shift, name="new_shift"),              # nút + Tạo ca mới
    path("chon-goi/", views.choose, name="choose"),                      # Tab 2: UC_4.1
    path("kiem-tra-ton-kho/", views.check, name="check"),                # Tab 3: UC_4.1.1
    path("bat-dau-ca/", views.start, name="start"),                      # Tab 4: UC_4.2
    path("tru-kho/", views.deduct, name="deduct"),                       # Tab 5: UC_4.2.1
    path("ca/<int:pk>/hoan-thanh/", views.complete, name="complete"),    # Luồng A1
    path("ca/<int:pk>/huy/", views.cancel, name="cancel"),               # Luồng A2
    path("nhap-nhanh/", views.quick_import, name="quick_import"),        # + Nhập kho nhanh
    path("reset-demo/", views.reset_demo, name="reset_demo"),
]
