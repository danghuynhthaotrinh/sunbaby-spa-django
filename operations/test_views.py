from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from inventory.models import Supplier, Item
from .models import DocumentSequence
from .models import LinenTracking, LaundryShipment
from .business import LaundryService


class OperationsWebTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username='op_manager', password='test-password', role='QUAN_LY',full_name='Quản lý')
        self.staff = get_user_model().objects.create_user(username='op_staff', role='KTV')
        self.supplier = Supplier.objects.create(code='GIAT-UI', name='Xưởng giặt UI', supplier_type='LAUNDRY')
        self.item = Item.objects.create(sku='LIN-UI',name='Khăn quấn',category='CAT-LIN',standard_unit='cái',is_linen=True,stock=10,min_stock=15)
        self.tracking = LinenTracking.objects.create(item=self.item,clean_qty=10,dirty_qty=25)
        self.client.force_login(self.manager)
        self.now = timezone.localtime().replace(second=0,microsecond=0)
        self.home = reverse('operations_home')

    def send_data(self, **extra):
        data=dict(supplier=self.supplier.pk,responsible=self.manager.pk,
            sent_at=self.now.strftime('%Y-%m-%dT%H:%M'),expected_at=(self.now+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            **{'send-TOTAL_FORMS':'1','send-INITIAL_FORMS':'0','send-0-item':self.item.pk,
               'send-0-sent_qty':'10','send-0-dirty_qty_snapshot':'25'})
        data.update(extra)
        return data

    def shipment(self):
        return LaundryService.send(user=self.manager,supplier_id=self.supplier.pk,responsible_id=self.manager.pk,
            sent_at=self.now,expected_at=self.now+timedelta(days=1),lines=[dict(item_id=self.item.pk,sent_qty=10,dirty_qty_snapshot=25)])

    def receive_data(self, shipment, qty='7', note='Thiếu 3 khăn', **extra):
        data={'received_at':self.now.strftime('%Y-%m-%dT%H:%M'),'version':shipment.version,
            'receive-TOTAL_FORMS':'1','receive-INITIAL_FORMS':'1','receive-0-item_id':self.item.pk,
            'receive-0-received_qty':qty,'receive-0-loss_note':note}
        data.update(extra)
        return data

    def test_auth_and_role(self):
        self.client.logout()
        r=self.client.get(self.home)
        self.assertRedirects(r,reverse('operations_login')+'?next=/operations/',fetch_redirect_response=False)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.home).status_code,403)

    def test_manager_can_login_without_admin_staff_flag(self):
        self.client.logout()
        r=self.client.post(reverse('operations_login'),{'username':'op_manager','password':'test-password','next':self.home})
        self.assertRedirects(r,self.home)

    def test_three_tabs_and_read_only_gets(self):
        for path,text in [(self.home,'Tổng quan tồn kho'),(self.home+'?tab=send','Xác nhận xuất giặt'),(self.home+'?tab=receive','Tổng hợp thất thoát')]:
            response=self.client.get(path)
            self.assertContains(response,text)
        self.assertEqual(DocumentSequence.objects.count(),0)
        self.assertEqual(LaundryShipment.objects.count(),0)

    def test_send_from_web(self):
        r=self.client.post(self.home+'?tab=send',self.send_data())
        self.assertRedirects(r,self.home+'?tab=receive')
        self.tracking.refresh_from_db()
        self.assertEqual((self.tracking.dirty_qty,self.tracking.laundry_qty),(15,10))
        self.assertEqual(LaundryShipment.objects.get().sent_qty,10)

    def test_invalid_send_preserves_input(self):
        r=self.client.post(self.home+'?tab=send',self.send_data(**{'send-0-sent_qty':'26'}))
        self.assertContains(r,'Vượt số đồ bẩn hiện có (25).')
        self.assertContains(r,'value="26"')
        self.assertFalse(LaundryShipment.objects.exists())

    def test_stale_dirty_stock(self):
        self.tracking.dirty_qty=24;self.tracking.save()
        r=self.client.post(self.home+'?tab=send',self.send_data())
        self.assertContains(r,'Số lượng đồ bẩn đã thay đổi.')
        self.assertFalse(LaundryShipment.objects.exists())

    def test_zero_lines_duplicate_sku_and_deadline(self):
        for extra in [ {'send-TOTAL_FORMS':'0'}, {'send-0-DELETE':'on'},
            {'send-TOTAL_FORMS':'2','send-1-item':self.item.pk,'send-1-sent_qty':'1','send-1-dirty_qty_snapshot':'25'},
            {'expected_at':self.now.strftime('%Y-%m-%dT%H:%M')} ]:
            r=self.client.post(self.home+'?tab=send',self.send_data(**extra))
            self.assertEqual(r.status_code,200)
            self.assertFalse(LaundryShipment.objects.exists())

    def test_receive_and_supplement_via_http(self):
        s=self.shipment();url=reverse('operations_shipment_detail',args=[s.pk])+'?receive=1'
        r=self.client.get(url,headers={'X-Requested-With':'XMLHttpRequest'})
        self.assertContains(r,'value="10"')
        r=self.client.post(url,self.receive_data(s),headers={'X-Requested-With':'XMLHttpRequest'})
        self.assertEqual(r.json()['redirect'],self.home+'?tab=receive')
        s.refresh_from_db(); self.assertEqual(s.loss_qty,3)
        r=self.client.post(url,self.receive_data(s,qty='10',note=''),headers={'X-Requested-With':'XMLHttpRequest'})
        self.assertEqual(r.status_code,200)
        s.refresh_from_db();self.item.refresh_from_db();self.tracking.refresh_from_db()
        self.assertEqual((s.status,self.item.stock,self.tracking.laundry_qty),('COMPLETED',20,0))
        r=self.client.get(url,headers={'X-Requested-With':'XMLHttpRequest'})
        self.assertNotContains(r,'id="receive-form"')

    def test_receive_requires_note_and_date(self):
        s=self.shipment();url=reverse('operations_shipment_detail',args=[s.pk])
        for data,text in [(self.receive_data(s,note=''),'Cần ghi chú khi có thất thoát.'),
            (self.receive_data(s,received_at=''),'Vui lòng chọn ngày giờ nhận.'),
            (self.receive_data(s,qty='11'),'Nhập số nguyên từ 0 đến 10.')]:
            response=self.client.post(url,data,headers={'X-Requested-With':'XMLHttpRequest'})
            self.assertContains(response,text,status_code=422)
        s.refresh_from_db();self.assertEqual(s.status,'SENT')

    def test_stale_receipt_and_forged_completed_post(self):
        s=self.shipment();url=reverse('operations_shipment_detail',args=[s.pk])
        self.client.post(url,self.receive_data(s),headers={'X-Requested-With':'XMLHttpRequest'})
        r=self.client.post(url,self.receive_data(s,qty='10'),headers={'X-Requested-With':'XMLHttpRequest'})
        self.assertContains(r,'Phiếu đã thay đổi.',status_code=422)
        s.refresh_from_db()
        self.client.post(url,self.receive_data(s,qty='10',note=''))
        r=self.client.post(url,self.receive_data(s,qty='10',note=''))
        self.assertEqual(r.status_code,409)

    def test_view_only_and_xss_escaping(self):
        s=self.shipment()
        self.supplier.name='<script>alert(1)</script>';self.supplier.save()
        r=self.client.get(reverse('operations_shipment_detail',args=[s.pk]),headers={'X-Requested-With':'XMLHttpRequest'})
        self.assertContains(r,'Phiếu đang giặt tại xưởng, chưa nhận hàng.')
        self.assertNotContains(r,'id="receive-form"')
        self.assertNotContains(r,'<script>alert(1)</script>')
        self.assertContains(r,'&lt;script&gt;')

    def test_csrf_required_for_writes(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.manager)
        self.assertEqual(c.post(self.home,self.send_data()).status_code,403)

    def test_receive_rejects_missing_or_duplicate_lines(self):
        s=self.shipment();url=reverse('operations_shipment_detail',args=[s.pk])
        for extra in [{'receive-TOTAL_FORMS':'0'},
            {'receive-TOTAL_FORMS':'2','receive-1-item_id':self.item.pk,'receive-1-received_qty':'10'},
            {'receive-0-item_id':'999999'}]:
            response=self.client.post(url,self.receive_data(s,**extra),headers={'X-Requested-With':'XMLHttpRequest'})
            self.assertEqual(response.status_code,422)
        s.refresh_from_db();self.assertEqual(s.received_qty,0)

    def test_seed_is_idempotent_without_touching_existing_stock(self):
        from django.core.management import call_command
        from io import StringIO
        output=StringIO()
        call_command('seed_operations_demo',stdout=output)
        demo=Item.objects.get(sku='DEMO-LIN-01')
        self.assertEqual(demo.stock,390)
        demo.stock=389;demo.save()
        call_command('seed_operations_demo',stdout=output)
        demo.refresh_from_db();self.assertEqual(demo.stock,389)
        self.item.refresh_from_db();self.assertEqual(self.item.stock,10)
