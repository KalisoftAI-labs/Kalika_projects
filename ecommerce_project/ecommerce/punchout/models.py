# punchout/models.py

from django.db import models
from accounts.models import CustomUser


class PunchOutSession(models.Model):
    """
    Stores PunchOut session data since cookies don't work reliably in iframes.
    This allows us to retrieve return URL and buyer cookie when checking out.
    """
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    return_url = models.URLField(max_length=500)
    buyer_cookie = models.TextField()
    from_identity = models.CharField(max_length=255, default='UNKNOWN')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"PunchOut Session {self.session_key}"
    
    class Meta:
        ordering = ['-created_at']


class PunchOutOrder(models.Model):
    """
    Yeh aapka mukhya "Order" table hai.
    """
    # ▼▼▼ YAHAN SE 'BUYER NAME' MILTA HAI ▼▼▼
    # Jab order save hota hai, to us waqt jo user logged in hota hai (jaise 'ARIBABUYER_USER'),
    # woh yahan save ho jaata hai.
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    cxml_payload = models.TextField()

    def __str__(self):
        return f"PunchOut Order for {self.user.username} on {self.created_at.strftime('%Y-%m-%d')}"


class PunchOutOrderItem(models.Model):
    """
    Yeh aapka "Order ke Items" ka table hai.
    Har product ki detail yahan alag column me save hoti hai.
    """
    # Yeh batata hai ki yeh item kis order ka hissa hai
    order = models.ForeignKey(PunchOutOrder, related_name='items', on_delete=models.CASCADE)
    
    # ▼▼▼ ALAG-ALAG COLUMNS ▼▼▼
    product_title = models.CharField(max_length=255)       # <-- Product Name
    item_code = models.CharField(max_length=50)            # <-- Product Code
    quantity = models.IntegerField()                       # <-- Quantity
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) # <-- Price
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)   # <-- Net Price
    unit_of_measure = models.CharField(max_length=20)      # <-- Extra Detail
    unspsc = models.CharField(max_length=20)               # <-- Extra Detail

    def __str__(self):
        return f"{self.quantity} x {self.product_title}"