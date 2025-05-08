from django.db import models
from django.contrib.auth.models import User
from doc_system import settings

class Document(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
    ]

    DOCUMENT_TYPE_CHOICES = [
        ('approval', 'Approval Letter'),
        ('sla', 'SLA Document'),
        ('Uploaded', 'Uploaded Document'),
    ]

    DOCUMENT_SOURCE_CHOICES = [
        ('template', 'Use Template'),
        ('upload', 'Upload Document'),
        ('editor', 'Created in Editor'),
    ]

    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE_CHOICES)
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
    # uploaded_file = models.FileField(upload_to='documents/', blank=True, null=True)

    document_source = models.CharField(max_length=20, choices=DOCUMENT_SOURCE_CHOICES, default='template')

    email_sent = models.BooleanField(default=False)  # Track if email was sent

    def __str__(self):
        return f"{self.document_type} - {self.company_name}"


from django.contrib.auth.models import AbstractUser
from django.db import models

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    POSITION_CHOICES = [
        ("BDA", "Business Development Assistant"),
        ("BDM", "Business Development Manager"),
    ]
    
    position = models.CharField(max_length=3, choices=POSITION_CHOICES, blank=True, null=True)
    roles = models.ManyToManyField(Role, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)  # New phone number field
    smtp_email = models.EmailField(blank=True, null=True)  # SMTP Email for Sending
    smtp_password = models.CharField(max_length=255, blank=True, null=True)  # SMTP Password


class Folder(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class File(models.Model):
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to='uploads/')
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name

class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    documents = models.ManyToManyField('Document', blank=True)
    folder = models.ForeignKey('Folder', on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
