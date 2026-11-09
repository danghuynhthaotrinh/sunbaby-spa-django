from django.contrib import admin
from .models import ServiceOrder, LinenTracking, LaundryShipment

admin.site.register(ServiceOrder)
admin.site.register(LinenTracking)
admin.site.register(LaundryShipment)

