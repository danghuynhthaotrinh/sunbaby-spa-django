from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', TemplateView.as_view(template_name='management/management_home.html'), name='management_home'),
]
