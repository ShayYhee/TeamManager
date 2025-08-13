from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta

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
    SUB_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

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
    num_users = models.PositiveIntegerField(default=0)
    subscription_plan = models.ForeignKey("tenants.SubscriptionType", on_delete=models.SET_NULL, null=True, blank=True, default=None)
    subscription_status = models.CharField(max_length=20, choices=SUB_STATUS_CHOICES, default='inactive')

    def __str__(self):
        return self.name
    
class SubscriptionType(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.name} - ${self.price} for {self.duration} days"
    
class Subscription(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant}' current subscription: {self.subscription_type}"

    def save(self, *args, **kwargs):
        if self.start_date and self.plan:
            self.end_date = self.start_date + timedelta(days=self.plan.duration)
        super().save(*args, **kwargs)

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payments')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)  # From payment gateway
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # e.g., 'credit_card', 'paypal'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment of {self.amount} for {self.tenant} on {self.payment_date}"