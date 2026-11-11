from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(
        url='/management/dashboard/',
        permanent=False,
    )),
    path('accounts/', include('accounts.urls')),
    path('inventory/', include('inventory.urls')),
    path('services/', include('services.urls')),
    path('operations/', include('operations.urls')),
    path('shifts/', include('shifts.urls')),
    path('management/', include('management.urls')),
    path('kho/', RedirectView.as_view(
        url='/inventory/',
        permanent=False,
    )),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)