# -*- coding: utf-8 -*-
from django import forms
from django.forms import inlineformset_factory
from .models import VatTu, NhaCungCap, PhieuNhap, DongPhieuNhap


class VatTuForm(forms.ModelForm):
    class Meta:
        model = VatTu
        fields = "__all__"


class NhaCungCapForm(forms.ModelForm):
    class Meta:
        model = NhaCungCap
        fields = "__all__"


class PhieuForm(forms.ModelForm):
    class Meta:
        model = PhieuNhap
        fields = ["ncc", "ngay_nhap", "hinh_thuc_thanh_toan", "ghi_chu"]


class DongForm(forms.ModelForm):
    class Meta:
        model = DongPhieuNhap
        fields = ["vat_tu", "so_luong_nhap", "don_gia_mua", "han_su_dung"]


DongFormSet = inlineformset_factory(PhieuNhap, DongPhieuNhap, form=DongForm, extra=3, can_delete=True)
