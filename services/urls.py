from django.urls import path
from . import views

app_name = "services"

urlpatterns = [
    path("", views.home, name="home"),
    path("goi/", views.package_list, name="package_list"),
    path("goi/them/", views.package_save, name="package_create"),
    path("goi/<int:pk>/sua/", views.package_save, name="package_edit"),
    path("goi/<int:pk>/doi-trang-thai/", views.package_toggle, name="package_toggle"),
    path("goi/<int:pk>/bom/", views.bom_config, name="bom_config"),
    path("gia-von/", views.cost_list, name="cost_list"),
    path("gia-von/<int:pk>/", views.cost_detail, name="cost_detail"),
]
