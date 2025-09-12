from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('User', 'User'),
        ('PunchOut', 'PunchOut'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='User')
    
    # Buyer identifier ko unique aur indexed banaya gaya hai taaki lookup fast ho
    buyer_identifier = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        unique=True, 
        db_index=True  # Performance ke liye index add kiya gaya hai
    )

    def __str__(self):
        return self.username