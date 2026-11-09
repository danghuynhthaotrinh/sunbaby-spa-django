from django.urls import path
<<<<<<< HEAD
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    path('', login_required(TemplateView.as_view(template_name='inventory/inventory_home.html'), login_url='login'), name='inventory_home'),
=======
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
>>>>>>> 8bf68790b21ce4b9c792b01e3b766464edc3a481
]