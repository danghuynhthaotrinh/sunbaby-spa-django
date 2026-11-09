# -*- coding: utf-8 -*-
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import GoodsReceipt, GoodsReceiptDetail, Item, Supplier, TheKho


class InventoryUC2Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="manager", password="pw", role="MANAGER"
        )
        self.supplier = Supplier.objects.create(code="SUP-T", name="Nhà cung cấp thử")
        self.item = Item.objects.create(
            sku="TEST-1",
            name="Dầu thử",
            category="CAT-OIL",
            supplier=self.supplier,
            standard_unit="ml",
            import_unit="Can",
            conversion_rate=Decimal("5000"),
            stock=Decimal("0"),
        )

    def test_quy_doi_va_tang_ton(self):
        receipt = GoodsReceipt.objects.create(
            receipt_code="PN-TEST-001", supplier=self.supplier, created_by=self.user
        )
        detail = GoodsReceiptDetail.objects.create(
            receipt=receipt,
            item=self.item,
            import_qty=Decimal("2"),
            conversion_rate=self.item.conversion_rate,
            converted_qty=Decimal("10000"),
            import_price=Decimal("1500000"),
        )
        self.item.stock += detail.import_qty * detail.conversion_rate
        self.item.save()
        TheKho.objects.create(
            item=self.item,
            so_luong=detail.converted_qty,
            ton_cuoi=self.item.stock,
            chung_tu=receipt.receipt_code,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, Decimal("10000"))
        self.assertEqual(TheKho.objects.get().ton_cuoi, Decimal("10000"))

    def test_sku_trung(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Item.objects.create(
                sku="TEST-1", name="Trùng", category="CAT-OIL", standard_unit="ml"
            )
