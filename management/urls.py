from django.urls import path
from . import views

urlpatterns = [
    path('', views.management_entry, name='management_home'),
    path('dashboard/', views.uc6_dashboard, name='uc6_dashboard'),
    path('damage/create/', views.damage_create, name='damage_create'),
    path('review/', views.damage_review_list, name='damage_review_list'),
    path('review/<int:pk>/action/', views.damage_review_action, name='damage_review_action'),
    path('po/', views.po_list_create, name='po_list_create'),
    path('po/<int:pk>/status/', views.po_update_status, name='po_update_status'),
]
