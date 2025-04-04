from django.db import models
from django.contrib.auth.models import User
from doc_system import settings

class Document(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
    ]

    document_type = models.CharField(max_length=20, choices=[('approval', 'Approval Letter'), ('sla', 'SLA Document')])
    company_name = models.CharField(max_length=255)
    company_address = models.TextField()
    contact_person_name = models.CharField(max_length=255)
    contact_person_email = models.EmailField()
    contact_person_designation = models.CharField(max_length=255)
    sales_rep = models.CharField(max_length=255)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_documents")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_documents")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    word_file = models.FileField(upload_to="documents/word/")
    pdf_file = models.FileField(upload_to="documents/pdf/", null=True, blank=True)

    email_sent = models.BooleanField(default=False)  # Track if email was sent

    def __str__(self):
        return f"{self.document_type} - {self.company_name}"


from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("BDA", "Business Development Assistant"),
        ("BDM", "Business Development Manager"),
    ]
    role = models.CharField(max_length=3, choices=ROLE_CHOICES, default="BDA")
    phone_number = models.CharField(max_length=15, blank=True, null=True)  # New phone number field
    smtp_email = models.EmailField(blank=True, null=True)  # SMTP Email for Sending
    smtp_password = models.CharField(max_length=255, blank=True, null=True)  # SMTP Password
