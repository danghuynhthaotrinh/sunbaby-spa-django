"""Forms cho UC_5.2 và UC_5.2.1; backend luôn kiểm tra lại dữ liệu."""
from django import forms
from django.contrib.auth import get_user_model
from django.forms import BaseFormSet, formset_factory
from inventory.models import Supplier, Item
from .models import LinenTracking


class LocalDateTimeField(forms.DateTimeField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('input_formats', ['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'])
        kwargs.setdefault('widget', forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))
        kwargs.setdefault('error_messages', {'required': 'Vui lòng chọn ngày giờ.', 'invalid': 'Ngày giờ không hợp lệ.'})
        super().__init__(*args, **kwargs)


class ShipmentForm(forms.Form):
    supplier = forms.ModelChoiceField(label='Xưởng giặt', queryset=Supplier.objects.none(), empty_label='Chọn xưởng giặt',
        error_messages={'required': 'Vui lòng chọn xưởng giặt.', 'invalid_choice': 'Xưởng giặt không hợp lệ.'})
    responsible = forms.ModelChoiceField(label='Người phụ trách', queryset=get_user_model().objects.none(), empty_label='Chọn người phụ trách',
        error_messages={'required': 'Vui lòng chọn người phụ trách.'})
    sent_at = LocalDateTimeField(label='Ngày giờ giao')
    expected_at = LocalDateTimeField(label='Hạn nhận dự kiến')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(supplier_type='LAUNDRY').order_by('name')
        self.fields['responsible'].queryset = get_user_model().objects.filter(is_active=True).order_by('username')
        self.fields['responsible'].label_from_instance = lambda u: u.full_name or u.get_full_name() or u.username

    def clean(self):
        data = super().clean()
        if data.get('sent_at') and data.get('expected_at') and data['expected_at'] <= data['sent_at']:
            self.add_error('expected_at', 'Hạn nhận phải sau ngày giờ giao.')
        return data


class ShipmentLineForm(forms.Form):
    item = forms.ModelChoiceField(queryset=Item.objects.none(), label='Loại đồ vải', empty_label='Chọn loại đồ vải',
        error_messages={'required': 'Vui lòng chọn loại đồ vải.', 'invalid_choice': 'Loại đồ vải không hợp lệ.'})
    sent_qty = forms.IntegerField(label='Số lượng giao', min_value=1,
        error_messages={'required': 'Nhập số nguyên lớn hơn 0.', 'invalid': 'Nhập số nguyên lớn hơn 0.', 'min_value': 'Nhập số nguyên lớn hơn 0.'})
    dirty_qty_snapshot = forms.IntegerField(min_value=0, widget=forms.HiddenInput,
        error_messages={'required': 'Vui lòng chọn lại loại đồ vải để lấy tồn hiện tại.'})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = Item.objects.filter(is_linen=True).order_by('sku')
        self.fields['item'].widget.attrs['aria-label'] = 'Loại đồ vải'
        self.fields['sent_qty'].widget.attrs['aria-label'] = 'Số lượng giao'
        # Kể cả dòng ban đầu chưa thay đổi cũng phải được validate.
        self.empty_permitted = False

    def clean(self):
        data = super().clean()
        item = data.get('item')
        qty = data.get('sent_qty')
        if item is not None:
            record = LinenTracking.objects.filter(item=item).first()
            available = record.dirty_qty if record else 0
            if qty is not None and qty > available:
                self.add_error('sent_qty', f'Vượt số đồ bẩn hiện có ({available}).')
        return data


class BaseShipmentLineSet(BaseFormSet):
    default_error_messages = {'too_few_forms': 'Chưa có dòng đồ vải. Chọn “+ Thêm dòng” để bắt đầu.'}

    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if form.cleaned_data.get('DELETE'):
                continue
            item = form.cleaned_data.get('item')
            if item:
                if item.pk in seen:
                    form.add_error('item', 'SKU đã có ở dòng khác.')
                seen.add(item.pk)


ShipmentLineSet = formset_factory(ShipmentLineForm, formset=BaseShipmentLineSet,
    extra=0, min_num=1, validate_min=True, max_num=200, validate_max=True,
    absolute_max=200, can_delete=True)


class ReceiveForm(forms.Form):
    received_at = LocalDateTimeField(label='Ngày nhận thực tế',
        error_messages={'required': 'Vui lòng chọn ngày giờ nhận.', 'invalid': 'Ngày giờ nhận không hợp lệ.'})
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class ReceiveLineForm(forms.Form):
    item_id = forms.IntegerField(widget=forms.HiddenInput)
    received_qty = forms.IntegerField(label='SL thực nhận', min_value=0)
    loss_note = forms.CharField(label='Ghi chú thất thoát', max_length=250, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Ghi chú nếu thiếu hàng', 'maxlength': 250}))


class BaseReceiveLineSet(BaseFormSet):
    def __init__(self, *args, details, **kwargs):
        self.details_by_id = {d.item_id: d for d in details}
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.empty_permitted = False
            raw_id = form['item_id'].value()
            try:
                detail = self.details_by_id.get(int(raw_id))
            except (TypeError, ValueError):
                detail = None
            form.detail = detail
            if detail is not None:
                minimum, maximum = detail.received_qty, detail.sent_qty
                field = form.fields['received_qty']
                # Server range check remains in clean(); attributes also power live validation.
                field.widget.attrs.update(min=minimum, max=maximum, step=1)
                field.widget.attrs['aria-label'] = f'SL thực nhận {detail.item.sku}'
                form.fields['loss_note'].widget.attrs['aria-label'] = f'Ghi chú thất thoát {detail.item.sku}'
                field.error_messages.update(required=f'Nhập số nguyên từ {minimum} đến {maximum}.',
                    invalid=f'Nhập số nguyên từ {minimum} đến {maximum}.',
                    min_value=f'Nhập số nguyên từ {minimum} đến {maximum}.')

    def clean(self):
        super().clean()
        submitted = []
        for form in self.forms:
            data = form.cleaned_data
            pk = data.get('item_id')
            detail = self.details_by_id.get(pk)
            submitted.append(pk)
            if detail is None:
                form.add_error('item_id', 'Dòng đồ vải không thuộc phiếu.')
                continue
            qty = data.get('received_qty')
            if qty is not None:
                if not detail.received_qty <= qty <= detail.sent_qty:
                    form.add_error('received_qty', f'Nhập số nguyên từ {detail.received_qty} đến {detail.sent_qty}.')
                elif qty < detail.sent_qty and not data.get('loss_note', '').strip():
                    form.add_error('loss_note', 'Cần ghi chú khi có thất thoát.')
        if len(submitted) != len(set(submitted)) or set(submitted) != set(self.details_by_id):
            raise forms.ValidationError('Phải gửi đủ các dòng đồ vải, không trùng SKU.')


ReceiveLineSet = formset_factory(ReceiveLineForm, formset=BaseReceiveLineSet,
    extra=0, max_num=200, validate_max=True, absolute_max=200)
