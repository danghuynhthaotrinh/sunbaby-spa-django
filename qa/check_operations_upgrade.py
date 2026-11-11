"""Chạy trên DB tạm: xác minh giữ dữ liệu từ schema main cũ sang phiếu nhiều SKU."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from django.conf import settings
with TemporaryDirectory() as temp:
    settings.DATABASES['default']['NAME']=str(Path(temp)/'upgrade.sqlite3')
    import django
    django.setup()
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    executor=MigrationExecutor(connection)
    old=[('accounts','0002_alter_user_options_user_lock_reason_and_more'),
        ('inventory','0004_thekho'),('services','0001_initial'),
        ('operations','0001_initial'),('management','0001_initial')]
    executor.migrate(old)
    apps=executor.loader.project_state(old).apps
    supplier=apps.get_model('inventory','Supplier').objects.create(code='GIAT-OLD',name='Xưởng cũ',supplier_type='LAUNDRY')
    item=apps.get_model('inventory','Item').objects.create(sku='LIN-OLD',name='Khăn cũ',category='CAT-LIN',
        standard_unit='cái',is_linen=True,stock=5)
    apps.get_model('operations','LinenTracking').objects.create(item_id=item.pk,clean_qty=5,dirty_qty=20,laundry_qty=10)
    OldShipment=apps.get_model('operations','LaundryShipment')
    OldShipment.objects.create(shipment_code='GIAT-OLD-01',supplier_id=supplier.pk,item_id=item.pk,sent_qty=10,status='SENT')
    OldShipment.objects.create(shipment_code='GIAT-OLD-02',supplier_id=supplier.pk,item_id=item.pk,sent_qty=10,
        received_qty=7,loss_qty=3,status='DISCREPANCY')
    executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
    from operations.models import LaundryShipment,LaundryShipmentDetail,LinenTracking
    from inventory.models import Item
    assert LaundryShipment.objects.count()==2 and LaundryShipmentDetail.objects.count()==2
    partial=LaundryShipment.objects.get(shipment_code='GIAT-OLD-02')
    assert (partial.sent_qty,partial.received_qty,partial.loss_qty)==(10,7,3)
    assert partial.is_legacy and partial.received_at is None and partial.expected_at is None
    assert partial.details.get().item_id==item.pk
    assert Item.objects.get(pk=item.pk).stock==5
    assert LinenTracking.objects.get(item_id=item.pk).laundry_qty==10
    print('PASS: migrated old shipments without losing codes, SKU, quantities or stock; unknown dates stay empty.')
    connection.close()
