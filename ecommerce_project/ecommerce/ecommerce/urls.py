from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # path('admin', RedirectView.as_view(url='/admin/', permanent=True)),
    # path('django-admin/', admin.site.urls), 
    path('admin/', admin.site.urls),
    path('', include('catalog.urls')),
    path('cart/', include('cart.urls')),
    path('accounts/', include('accounts.urls')),
    path('punchout/', include('punchout.urls')),
]