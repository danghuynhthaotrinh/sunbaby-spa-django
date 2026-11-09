from django.shortcuts import render
from inventory.models import Item
from operations.models import ServiceOrder
from .models import DamageReport, PurchaseOrder

def dashboard(request):
    context = {
        'total_items': Item.objects.count(),
        'total_orders': ServiceOrder.objects.count(),
        'pending_po': PurchaseOrder.objects.filter(status='PENDING').count(),
        'damage_count': DamageReport.objects.count(),
    }
    return render(request, 'management/dashboard.html', context)
