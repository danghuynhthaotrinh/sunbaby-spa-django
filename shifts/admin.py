from django.contrib import admin

from .models import ServiceOrderDetail, ServiceOrderLine


@admin.register(ServiceOrderDetail)
class ServiceOrderDetailAdmin(admin.ModelAdmin):
    list_display = ("order", "customer_name", "customer_phone", "issue_code")


@admin.register(ServiceOrderLine)
class ServiceOrderLineAdmin(admin.ModelAdmin):
    list_display = ("order", "item", "quantity", "is_linen")
