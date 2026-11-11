from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from inventory.models import Supplier, Item, TheKho
from services.models import ServicePackage, BOMItem
from .business import LaundryService
from .models import LinenTracking, ServiceOrder

class CurrentRepositoryIntegrationTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='quanly',password='test-password',role='QUAN_LY')
        self.supplier=Supplier.objects.create(code='GIAT-I',name='Xưởng I',supplier_type='LAUNDRY')
        self.item=Item.objects.create(sku='LIN-I',name='Khăn',category='CAT-LIN',standard_unit='cái',is_linen=True,stock=10)
        self.tracking=LinenTracking.objects.create(item=self.item,clean_qty=10,dirty_qty=25)
        self.client.force_login(self.user)

    def test_new_role_names_are_accepted(self):
        for role in ['QUAN_LY','THU_KHO','ADMIN']:
            self.user.role=role;self.user.save()
            self.assertEqual(self.client.get('/operations/').status_code,200)
        for role in ['LE_TAN','KTV']:
            self.user.role=role;self.user.save()
            self.assertEqual(self.client.get('/operations/').status_code,403)

    def test_real_inventory_and_legacy_redirect(self):
        self.assertEqual(self.client.get('/inventory/').status_code,200)
        self.assertRedirects(self.client.get('/kho/'),'/inventory/')

    def test_service_package_and_bom_are_preserved(self):
        package=ServicePackage.objects.create(ma_goi='GOI-I',ten='Gói nhóm',gia_ban=200000)
        BOMItem.objects.create(goi=package,vat_tu=self.item,dinh_luong=1)
        order=ServiceOrder.objects.create(order_code='CA-I',service=package,staff=self.user)
        self.assertEqual(order.service.bom_items.get().vat_tu_id,self.item.pk)
        self.assertEqual(reverse('services:package_list'),'/services/goi/')

    def test_warehouse_receipt_syncs_existing_clean_tracking(self):
        goods=Supplier.objects.create(code='NCC-I',name='NCC')
        response=self.client.post(reverse('inventory_receive'),{
            'supplier':goods.pk,'payment_method':'Tiền mặt','note':'Giữ form kho',
            'details-TOTAL_FORMS':'1','details-INITIAL_FORMS':'0',
            'details-0-item':self.item.pk,'details-0-import_qty':'2','details-0-import_price':'10000',
        })
        self.assertEqual(response.status_code,302)
        self.item.refresh_from_db();self.tracking.refresh_from_db()
        self.assertEqual((self.item.stock,self.tracking.clean_qty),(12,12))
        self.assertEqual(TheKho.objects.get().ton_cuoi,12)

    def test_receipt_delta_updates_moved_ledger_once(self):
        now=timezone.now()
        shipment=LaundryService.send(user=self.user,supplier_id=self.supplier.pk,responsible_id=self.user.pk,
            sent_at=now,expected_at=now+timedelta(days=1),
            lines=[dict(item_id=self.item.pk,sent_qty=10,dirty_qty_snapshot=25)])
        shipment=LaundryService.receive(user=self.user,shipment_id=shipment.pk,received_at=now,version=0,
            lines=[dict(item_id=self.item.pk,received_qty=7,loss_note='Thiếu 3')])
        shipment=LaundryService.receive(user=self.user,shipment_id=shipment.pk,received_at=now,version=shipment.version,
            lines=[dict(item_id=self.item.pk,received_qty=10,loss_note='')])
        self.assertEqual(list(TheKho.objects.order_by('id').values_list('so_luong','ton_cuoi')),[(7,17),(3,20)])
        self.tracking.refresh_from_db();self.assertEqual(self.tracking.laundry_qty,0)

    def test_noninteger_linen_is_rejected_before_item_write(self):
        from django.core.exceptions import ValidationError
        self.item.stock='0.5'
        with self.assertRaises(ValidationError):self.item.save(update_fields=['stock'])
        self.item.refresh_from_db();self.assertEqual(self.item.stock,10)
