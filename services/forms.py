from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from inventory.models import Item
from .models import BOMItem, ServicePackage


class ServicePackageForm(forms.ModelForm):
    class Meta:
        model = ServicePackage
        fields = ["ma_goi", "ten", "nhom", "thoi_luong_phut",
                  "gia_ban", "mo_ta", "dang_ban"]
        widgets = {"mo_ta": forms.Textarea(attrs={"rows": 3})}
        error_messages = {
            "ma_goi": {"required": "Vui lòng nhập mã gói.",
                       "unique": "Mã gói đã tồn tại."},
            "ten": {"required": "Vui lòng nhập tên gói."},
            "gia_ban": {"required": "Vui lòng nhập giá bán.",
                        "invalid": "Giá bán không hợp lệ."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:                      # BR1: không sửa mã gói
            self.fields["ma_goi"].disabled = True


class BOMItemForm(forms.ModelForm):
    class Meta:
        model = BOMItem
        fields = ["vat_tu", "dinh_luong"]
        error_messages = {
            "dinh_luong": {"invalid": "Định mức không hợp lệ."},
        }


class BaseBOMFormSet(BaseInlineFormSet):
    def clean(self):
        if any(self.errors):
            return
        da_co, so_dong = set(), 0
        for form in self.forms:
            cd = getattr(form, "cleaned_data", None)
            if not cd or cd.get("DELETE") or not cd.get("vat_tu"):
                continue
            if cd["vat_tu"].pk in da_co:          # E2 / BR3
                raise forms.ValidationError(
                    f"Vật tư “{cd['vat_tu']}” đã có trong BOM, "
                    "hãy sửa định mức ở dòng đã có.")
            da_co.add(cd["vat_tu"].pk)
            so_dong += 1
        if so_dong == 0:                           # E3 / BR4
            raise forms.ValidationError("BOM phải có ít nhất một vật tư.")


BOMFormSet = inlineformset_factory(
    ServicePackage, BOMItem,
    form=BOMItemForm, formset=BaseBOMFormSet,
    extra=1, can_delete=True,
)


class DonGiaVonForm(forms.Form):
    vat_tu = forms.ModelChoiceField(Item.objects.all(), label="Vật tư")
    don_gia_von = forms.DecimalField(
        label="Đơn giá vốn / đơn vị chuẩn (đ)",
        min_value=0, max_digits=14, decimal_places=2,
        error_messages={"invalid": "Đơn giá không hợp lệ.",
                        "min_value": "Đơn giá phải lớn hơn hoặc bằng 0."},
    )