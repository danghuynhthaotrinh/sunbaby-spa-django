# -*- coding: utf-8 -*-
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import NhaCungCap, NhomVatTu, VatTu, PhieuNhap, DongPhieuNhap, TheKho


class KhoTests(TestCase):
    def setUp(self):
        self.ncc = NhaCungCap.objects.create(ma_ncc="NCC-T", ten="Nhà cung cấp thử")
        self.nhom = NhomVatTu.objects.create(ma_nhom="CAT-T", ten="Nhóm thử")
        self.vat_tu = VatTu.objects.create(sku="SKU-T", ten="Vật tư thử", nhom=self.nhom, don_vi_nhap="Can", don_vi_chuan="ml", ty_le_quy_doi=Decimal("5000"), don_gia_nhap=Decimal("1500000"))
        self.user = get_user_model().objects.create_user(username="thukho", password="test-pass")

    def test_quy_doi_don_vi(self):
        phieu = PhieuNhap.objects.create(ncc=self.ncc, nguoi_nhap=self.user, hinh_thuc_thanh_toan="Tiền mặt")
        dong = DongPhieuNhap.objects.create(phieu=phieu, vat_tu=self.vat_tu, so_luong_nhap=Decimal("2"), don_gia_mua=Decimal("1500000"))
        self.assertEqual(dong.so_luong_quy_doi, Decimal("10000"))
        self.assertEqual(self.vat_tu.gia_von_don_vi_chuan, Decimal("300"))

    def test_nhap_cong_ton_va_tao_the_kho(self):
        phieu = PhieuNhap.objects.create(ncc=self.ncc, nguoi_nhap=self.user, hinh_thuc_thanh_toan="Chuyển khoản")
        dong = DongPhieuNhap.objects.create(phieu=phieu, vat_tu=self.vat_tu, so_luong_nhap=Decimal("2"), don_gia_mua=Decimal("1500000"))
        self.vat_tu.ton_kha_dung += dong.so_luong_quy_doi
        self.vat_tu.save(update_fields=["ton_kha_dung"])
        TheKho.objects.create(vat_tu=self.vat_tu, so_luong=dong.so_luong_quy_doi, ton_cuoi=self.vat_tu.ton_kha_dung, chung_tu=phieu.ma_phieu)
        self.vat_tu.refresh_from_db()
        self.assertEqual(self.vat_tu.ton_kha_dung, Decimal("10000"))
        self.assertEqual(TheKho.objects.get().ton_cuoi, Decimal("10000"))

    def test_trung_sku_bi_tu_choi(self):
        with self.assertRaises(Exception):
            VatTu.objects.create(sku="SKU-T", ten="Trùng", nhom=self.nhom, don_vi_nhap="Hộp", don_vi_chuan="cái", ty_le_quy_doi=1)

    def test_ty_le_khong_duong_bi_tu_choi(self):
        self.vat_tu.ty_le_quy_doi = Decimal("0")
        with self.assertRaises(ValidationError):
            self.vat_tu.full_clean()
