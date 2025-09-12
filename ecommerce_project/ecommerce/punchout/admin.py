# punchout/admin.py

from django.contrib import admin
from .models import PunchOutOrder, PunchOutOrderItem

class PunchOutOrderItemInline(admin.TabularInline):
    """
    Allows viewing order items directly within the PunchOutOrder admin page.
    This is configured to be read-only as it's a log.
    """
    model = PunchOutOrderItem
    # Fields to display in the inline view
    fields = ('product_title', 'item_code', 'quantity', 'unit_price', 'subtotal', 'unspsc')
    readonly_fields = fields
    can_delete = False
    extra = 0 # No extra blank forms

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PunchOutOrder)
class PunchOutOrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_cost', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('user__username', 'cxml_payload')
    
    # Fields to display on the main order page, configured as read-only.
    readonly_fields = ('user', 'total_cost', 'created_at', 'cxml_payload')
    
    # Add the inline view for order items
    inlines = [PunchOutOrderItemInline]

    def has_add_permission(self, request):
        # Prevent manual creation of new order logs from the admin.
        return False

    def has_change_permission(self, request, obj=None):
        # Prevent editing of order logs from the admin.
        return False