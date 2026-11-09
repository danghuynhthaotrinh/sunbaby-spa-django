# -*- coding: utf-8 -*-
from django.urls import path
from . import views
app_name="kho"
urlpatterns=[path("",views.index,name="index"),path("vat-tu/them/",views.vat_tu_form,name="vat_tu_add"),path("vat-tu/<int:pk>/",views.vat_tu_form,name="vat_tu_edit"),path("vat-tu/<int:pk>/xoa/",views.vat_tu_delete,name="vat_tu_delete"),path("ncc/",views.ncc_form,name="ncc"),path("nhap/",views.nhap_kho,name="nhap"),path("phieu/<int:pk>/",views.phieu_detail,name="phieu")]
