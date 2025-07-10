from django.db import models
from django.contrib.auth.models import AbstractUser

# class SuperUser(AbstractUser):
#     pass

class TenantApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    organization_name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization_name} ({self.status})"

class Tenant(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'documents.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tenants'
    )
    admin = models.ForeignKey(
        'documents.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_tenants'
    )
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.name