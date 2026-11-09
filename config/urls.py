
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('management/', include('management.urls')),
    path('inventory/', include('inventory.urls')),
    path('services/', include('services.urls')),
    path('operations/', include('operations.urls')),
    path('shifts/', include('shifts.urls')),
    path('', lambda request: redirect('login')),
]

