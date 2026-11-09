# -*- coding: utf-8 -*-
from decimal import Decimal
from django.core.management.base import BaseCommand
from inventory.models import Item, Supplier

class Command(BaseCommand):
    help = "Seed mẫu UC_2 vào inventory."
    def handle(self, *args, **options):
        suppliers = []
        for i, name in enumerate(["Mỹ phẩm An Nhiên", "Vải spa Minh Tâm", "Vật tư y tế Hoa Sen", "Đồ uống Việt"], 1):
            obj, _ = Supplier.objects.update_or_create(code=f"NCC-{i:02d}", defaults={"name": name, "supplier_type": "GOODS"})
            suppliers.append(obj)
        rows = [("OIL-01","Tinh dầu bưởi massage body","CAT-OIL","Can 5 Lít","ml",5000,1500000), ("OIL-02","Tinh dầu oải hương","CAT-OIL","Can 5 Lít","ml",5000,1800000), ("OIL-03","Dầu massage hạnh nhân","CAT-OIL","Can 5 Lít","ml",5000,2100000), ("SCR-01","Muối tẩy tế bào chết","CAT-OIL","Hũ 2 kg","g",2000,260000), ("SHA-01","Dầu gội thảo mộc","CAT-OIL","Can 5 Lít","ml",5000,650000), ("LIN-01","Khăn trải giường lớn","CAT-LIN","Thùng 50 cái","cái",50,1250000)]
        for i, (sku, name, cat, unit, standard, rate, price) in enumerate(rows):
            Item.objects.update_or_create(sku=sku, defaults={"name":name,"category":cat,"supplier":suppliers[i%4],"import_unit":unit,"standard_unit":standard,"conversion_rate":Decimal(rate),"import_price":Decimal(price),"min_stock":10,"is_linen":cat=="CAT-LIN"})
        self.stdout.write(self.style.SUCCESS("Đã nạp vật tư mẫu."))
