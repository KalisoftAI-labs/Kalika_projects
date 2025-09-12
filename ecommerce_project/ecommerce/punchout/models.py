# punchout/models.py

from django.db import models
from accounts.models import CustomUser

class PunchOutOrder(models.Model):
    """
    PunchOut session se generate hue har order ka ek high-level record.
    Isme order ki summary aur raw cXML payload audit ke liye store hota hai.
    """
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    cxml_payload = models.TextField(help_text="The raw cXML payload sent back to the procurement system for audit purposes.")

    def __str__(self):
        return f"PunchOut Order for {self.user.username} on {self.created_at.strftime('%Y-%m-%d')}"

class PunchOutOrderItem(models.Model):
    """
    Ek PunchOutOrder ke andar har individual item ki details.
    Yeh model data analysis ke liye structured data store karta hai.
    """
    order = models.ForeignKey(PunchOutOrder, related_name='items', on_delete=models.CASCADE)
    product_title = models.CharField(max_length=255)
    item_code = models.CharField(max_length=50, help_text="Corresponds to SupplierPartID in cXML")
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=20)
    unspsc = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.quantity} x {self.product_title}"