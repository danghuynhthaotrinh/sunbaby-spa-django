from django.contrib import admin
from .models import ServiceOrder, LinenTracking, LaundryShipment, LaundryShipmentDetail

class ReadOnlyTransactionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

admin.site.register(ServiceOrder)
for model in (LinenTracking, LaundryShipment, LaundryShipmentDetail):
    admin.site.register(model, ReadOnlyTransactionAdmin)
