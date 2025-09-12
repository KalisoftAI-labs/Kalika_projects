from django.urls import path
from . import views

app_name = 'punchout'

urlpatterns = [
    path('setup/', views.punchout_setup, name='punchout-setup'),
    path('return-cart/', views.return_cart_to_ariba, name='return-cart'),
]