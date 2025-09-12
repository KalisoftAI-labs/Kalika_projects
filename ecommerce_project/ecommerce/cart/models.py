# cart/models.py (Naya aur Sahi Code)

from django.db import models
from catalog.models import Product

class CartItem(models.Model):
    session_key = models.CharField(max_length=40, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.product_title}"

    @property
    def subtotal(self):
        """
        Har cart item ke liye subtotal calculate karta hai.
        Subtotal = quantity * product's price
        """
        return self.quantity * self.product.price