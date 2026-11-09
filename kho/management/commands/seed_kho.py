# -*- coding: utf-8 -*-
from decimal import Decimal
from django.core.management.base import BaseCommand
from kho.models import NhaCungCap, NhomVatTu, VatTu


class Command(BaseCommand):
    help = "Tạo dữ liệu mẫu cho danh mục kho Sun Baby."

    def handle(self, *args, **options):
        nhom_data = [
            ("CAT-OIL", "Tinh dầu & Kem mỹ phẩm"),
            ("CAT-LIN", "Đồ vải luân chuyển"),
            ("CAT-DIS", "Vật tư tiêu hao 1 lần"),
            ("CAT-BEA", "Phụ liệu chăm sóc chuyên sâu"),
            ("CAT-FNB", "Đồ uống & Tiếp đón"),
        ]
        nhoms = {ma: NhomVatTu.objects.update_or_create(ma_nhom=ma, defaults={"ten": ten})[0] for ma, ten in nhom_data}
        nccs = []
        for i, ten in enumerate(["Mỹ phẩm thiên nhiên An Nhiên", "Vải spa Minh Tâm", "Vật tư y tế Hoa Sen", "Đồ uống Tiếp đón Việt"], 1):
            nccs.append(NhaCungCap.objects.update_or_create(ma_ncc=f"NCC-{i:02d}", defaults={"ten": ten, "sdt": f"090000000{i}"})[0])
        data = [
            ("OIL-01", "Tinh dầu bưởi massage body", "CAT-OIL", "Can 5 Lít", "ml", 5000, 1500000),
            ("OIL-02", "Tinh dầu oải hương", "CAT-OIL", "Can 5 Lít", "ml", 5000, 1800000),
            ("OIL-03", "Dầu massage hạnh nhân", "CAT-OIL", "Can 5 Lít", "ml", 5000, 2100000),
            ("OIL-04", "Kem dưỡng thể", "CAT-OIL", "Hũ 1 kg", "g", 1000, 420000),
            ("OIL-05", "Gel nha đam", "CAT-OIL", "Can 5 Lít", "ml", 5000, 650000),
            ("LIN-01", "Khăn trải giường lớn", "CAT-LIN", "Thùng 50 cái", "cái", 50, 1250000),
            ("LIN-02", "Khăn tắm cotton", "CAT-LIN", "Thùng 50 cái", "cái", 50, 950000),
            ("LIN-03", "Khăn mặt spa", "CAT-LIN", "Thùng 100 cái", "cái", 100, 800000),
            ("LIN-04", "Áo choàng spa", "CAT-LIN", "Thùng 20 cái", "cái", 20, 1600000),
            ("DIS-01", "Găng tay dùng một lần", "CAT-DIS", "Hộp 100 cái", "cái", 100, 35000),
            ("DIS-02", "Khẩu trang y tế", "CAT-DIS", "Hộp 50 cái", "cái", 50, 28000),
            ("DIS-03", "Tăm bông", "CAT-DIS", "Túi 200 cái", "cái", 200, 22000),
            ("DIS-04", "Giấy lót giường", "CAT-DIS", "Cuộn 100 m", "m", 100, 90000),
            ("DIS-05", "Mũ trùm tóc", "CAT-DIS", "Túi 100 cái", "cái", 100, 40000),
            ("BEA-01", "Đá nóng massage", "CAT-BEA", "Thùng 20 viên", "viên", 20, 500000),
            ("BEA-02", "Bột thảo dược ngâm chân", "CAT-BEA", "Túi 1 kg", "g", 1000, 180000),
            ("BEA-03", "Mặt nạ dưỡng da", "CAT-BEA", "Hộp 10 miếng", "miếng", 10, 120000),
            ("BEA-04", "Muối tẩy tế bào chết", "CAT-BEA", "Hũ 2 kg", "g", 2000, 260000),
            ("FNB-01", "Nước suối", "CAT-FNB", "Thùng 24 chai", "chai", 24, 72000),
            ("FNB-02", "Trà thảo mộc tiếp đón", "CAT-FNB", "Hộp 50 gói", "gói", 50, 95000),
        ]
        for i, (sku, ten, ma_nhom, don_vi, chuan, ty_le, gia) in enumerate(data):
            VatTu.objects.update_or_create(sku=sku, defaults={"ten": ten, "nhom": nhoms[ma_nhom], "don_vi_nhap": don_vi, "don_vi_chuan": chuan, "ty_le_quy_doi": Decimal(ty_le), "don_gia_nhap": Decimal(gia), "ton_toi_thieu": Decimal("10"), "ncc_mac_dinh": nccs[i % len(nccs)]})
        self.stdout.write(self.style.SUCCESS("Đã nạp 5 nhóm, 4 nhà cung cấp và 20 vật tư mẫu."))
