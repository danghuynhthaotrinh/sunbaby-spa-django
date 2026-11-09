# -*- coding: utf-8 -*-
from decimal import Decimal

from django.core.management.base import BaseCommand
from inventory.models import Item, Supplier
from kho.models import CATEGORIES


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu kho trong các model inventory."

    def handle(self, *args, **options):
        suppliers = []
        supplier_names = [
            "Mỹ phẩm An Nhiên",
            "Vải spa Minh Tâm",
            "Vật tư y tế Hoa Sen",
            "Đồ uống Việt",
        ]
        for index, name in enumerate(supplier_names, 1):
            supplier, _ = Supplier.objects.update_or_create(
                code=f"NCC-{index:02d}",
                defaults={
                    "name": name,
                    "phone": f"090000000{index}",
                    "supplier_type": "GOODS",
                },
            )
            suppliers.append(supplier)

        rows = [
            ("OIL-01", "Tinh dầu bưởi massage body", "CAT-OIL", "Can 5 Lít", "ml", 5000, 1500000, False),
            ("OIL-02", "Tinh dầu oải hương", "CAT-OIL", "Can 5 Lít", "ml", 5000, 1800000, False),
            ("OIL-03", "Dầu massage hạnh nhân", "CAT-OIL", "Can 5 Lít", "ml", 5000, 2100000, False),
            ("SCR-01", "Muối tẩy tế bào chết", "CAT-OIL", "Hũ 2 kg", "g", 2000, 260000, False),
            ("SHA-01", "Dầu gội thảo mộc", "CAT-OIL", "Can 5 Lít", "ml", 5000, 650000, False),
            ("LIN-01", "Khăn trải giường lớn", "CAT-LIN", "Thùng 50 cái", "cái", 50, 1250000, True),
            ("LIN-02", "Khăn tắm cotton", "CAT-LIN", "Thùng 50 cái", "cái", 50, 950000, True),
            ("LIN-03", "Khăn mặt spa", "CAT-LIN", "Thùng 100 cái", "cái", 100, 800000, True),
            ("LIN-04", "Áo choàng spa", "CAT-LIN", "Thùng 20 cái", "cái", 20, 1600000, True),
            ("DIS-01", "Găng tay dùng một lần", "CAT-DIS", "Hộp 100 cái", "cái", 100, 35000, False),
            ("DIS-02", "Khẩu trang y tế", "CAT-DIS", "Hộp 50 cái", "cái", 50, 28000, False),
            ("DIS-03", "Tăm bông", "CAT-DIS", "Túi 200 cái", "cái", 200, 22000, False),
            ("DIS-04", "Giấy lót giường", "CAT-DIS", "Cuộn 100 m", "m", 100, 90000, False),
            ("DIS-05", "Mũ trùm tóc", "CAT-DIS", "Túi 100 cái", "cái", 100, 40000, False),
            ("BEA-01", "Đá nóng massage", "CAT-BEA", "Thùng 20 viên", "viên", 20, 500000, False),
            ("BEA-02", "Bột thảo dược ngâm chân", "CAT-BEA", "Túi 1 kg", "g", 1000, 180000, False),
            ("BEA-03", "Mặt nạ dưỡng da", "CAT-BEA", "Hộp 10 miếng", "miếng", 10, 120000, False),
            ("BEA-04", "Tinh chất chăm sóc da", "CAT-BEA", "Hộp 10 lọ", "lọ", 10, 320000, False),
            ("FNB-01", "Nước suối", "CAT-FNB", "Thùng 24 chai", "chai", 24, 72000, False),
            ("FNB-02", "Trà thảo mộc tiếp đón", "CAT-FNB", "Hộp 50 gói", "gói", 50, 95000, False),
        ]

        for index, (sku, name, category, import_unit, standard_unit, rate, price, is_linen) in enumerate(rows):
            Item.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "supplier": suppliers[index % len(suppliers)],
                    "import_unit": import_unit,
                    "standard_unit": standard_unit,
                    "conversion_rate": Decimal(rate),
                    "import_price": Decimal(price),
                    "min_stock": Decimal("10"),
                    "is_linen": is_linen,
                },
            )

        self.stdout.write(self.style.SUCCESS("Đã nạp 5 nhóm mã, 4 nhà cung cấp và 20 vật tư mẫu."))
