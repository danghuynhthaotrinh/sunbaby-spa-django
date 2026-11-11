"""Dữ liệu mô phỏng tách biệt bằng tiền tố DEMO; không sửa SKU hoặc tồn của nhóm."""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from inventory.models import Supplier, Item
from operations.models import LinenTracking
from inventory.models import TheKho

class Command(BaseCommand):
    help = 'Tạo 3 SKU DEMO và 1 xưởng DEMO để thử giao diện đồ vải; không tạo tài khoản.'

    @transaction.atomic
    def handle(self, *args, **options):
        codes = ['DEMO-LIN-01', 'DEMO-LIN-02', 'DEMO-LIN-03']
        existing = set(Item.objects.filter(sku__in=codes).values_list('sku', flat=True))
        if existing:
            self.stdout.write('Đã có SKU DEMO; không tạo lại hoặc ghi đè tồn: ' + ', '.join(sorted(existing)))
            return
        supplier, created = Supplier.objects.get_or_create(code='DEMO-GIAT-01',
            defaults={'name': 'Xưởng giặt Minh Tâm (DEMO)', 'supplier_type': 'LAUNDRY'})
        if supplier.supplier_type != 'LAUNDRY':
            raise CommandError('Mã DEMO-GIAT-01 đang thuộc đối tác khác loại; không sửa dữ liệu.')
        rows = [('DEMO-LIN-01','Khăn trải giường lớn',390,25,100),
                ('DEMO-LIN-02','Khăn quấn cotton',200,35,100),
                ('DEMO-LIN-03','Áo choàng spa',33,11,100)]
        for sku,name,clean,dirty,minimum in rows:
            item=Item(sku=sku,name=name,category='CAT-LIN',standard_unit='cái',import_unit='cái',
                      conversion_rate=Decimal('1'),stock=clean,min_stock=minimum,is_linen=True)
            item.full_clean();item.save()
            tracking=LinenTracking(item=item,clean_qty=clean,dirty_qty=dirty)
            tracking.full_clean();tracking.save()
            TheKho.objects.create(item=item,so_luong=clean,ton_cuoi=clean,chung_tu='DEMO-OPENING',
                                  loai_bien_dong='Tồn sạch đầu kỳ DEMO')
        self.stdout.write(self.style.SUCCESS('Đã tạo 3 loại đồ vải và 1 xưởng DEMO. Không tạo mật khẩu hoặc sửa dữ liệu thật.'))
