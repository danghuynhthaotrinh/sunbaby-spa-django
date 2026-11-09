from django.contrib import admin
from .models import BOMItem, ServicePackage


class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 0


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ("ma_goi", "ten", "gia_ban", "dang_ban")
    search_fields = ("ma_goi", "ten")
    inlines = [BOMItemInline]