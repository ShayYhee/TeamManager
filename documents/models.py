from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from raadaa import settings
from django.utils import timezone
import os
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet
from tenants.models import Tenant

# Generate or load encryption key for SMTP password
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY)


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

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
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
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    roles = models.ManyToManyField(Role, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    teams = models.ManyToManyField('Team', blank=True, related_name='members')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    smtp_email = models.EmailField(blank=True, null=True)
    smtp_password = models.CharField(max_length=255, blank=True, null=True)  # Encrypted SMTP password

    def set_smtp_password(self, password):
        """Encrypt and store SMTP password."""
        if password:
            self.smtp_password = cipher.encrypt(password.encode()).decode()
        else:
            self.smtp_password = None

    def get_smtp_password(self):
        """Decrypt and return SMTP password."""
        if self.smtp_password:
            return cipher.decrypt(self.smtp_password.encode()).decode()
        return None

    def clean(self):
        """Validate SMTP credentials."""
        if self.smtp_email and not self.smtp_password:
            raise ValidationError("SMTP password is required if SMTP email is provided.")
        if self.smtp_password and not self.smtp_email:
            raise ValidationError("SMTP email is required if SMTP password is provided.")

    def is_hod(self):
        return self.roles.filter(name='HOD').exists()

    def __str__(self):
        return self.username


class Folder(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
def upload_to_folder(instance, filename):
    folder_name = instance.folder.name if instance.folder else "unassigned"
    return os.path.join('uploads', folder_name, filename)


class File(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to=upload_to_folder)
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
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    documents = models.ManyToManyField('File', blank=True)
    folder = models.ForeignKey('Folder', on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# class Organization(models.Model):
#     name = models.CharField(max_length=255, unique=True)

#     def __str__(self):
#         return self.name
    
class Department(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    hod = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_department')

    def save(self, *args, **kwargs):
        if self.hod and not self.hod.is_hod():
            raise ValueError("HOD must have the 'HOD' role.")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
class Team(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, blank=True, null=True)
    team_leader = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='team_leader')

    def __str__(self):
        return self.name
    
class StaffProfile(models.Model):
    RELIGION_CHOICES = [
        ('islam', 'Islam'),
        ('christianity', 'Christianity'),
        ('other', 'Other'),
    ]
    SEX_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    EMERGENCY_RELATIONSHIP_CHOICES = [
        ('husband', 'Husband'),
        ('wife', 'Wife'),
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
    ]
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    photo = models.ImageField(upload_to='staff_photos/', null=True, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    home_address = models.CharField(max_length=255, null=True, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, null=True, blank=True)
    religion = models.CharField(max_length=15, choices=RELIGION_CHOICES, null=True, blank=True)
    state_of_origin = models.CharField(max_length=255, null=True, blank=True)
    lga = models.CharField(max_length=255, null=True, blank=True)
    marital_status = models.CharField(max_length=255, choices=MARITAL_STATUS_CHOICES, null=True, blank=True)
    institution = models.CharField(max_length=255, null=True, blank=True)
    course = models.CharField(max_length=255, null=True, blank=True)
    degree = models.CharField(max_length=100, null=True, blank=True)
    graduation_year = models.DateField(null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_name = models.CharField(max_length=100, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    employment_date = models.DateField(null=True, blank=True)
    official_email = models.EmailField(null=True, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff')
    team = models.ManyToManyField('Team', blank=True)
    emergency_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_relationship = models.CharField(max_length=20, choices=EMERGENCY_RELATIONSHIP_CHOICES, null=True, blank=True)
    emergency_phone = models.CharField(max_length=20, null=True, blank=True)
    emergency_address = models.TextField(null=True, blank=True)
    emergency_email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

class Notification(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # today = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class NotificationType(models.TextChoices):
        NEWS = 'news', 'News'
        BIRTHDAY = 'birthday', 'Birthday'
        ALERT = 'alert', 'Alert'
        EVENT = 'event', 'Event'

    type = models.CharField(max_length=20, choices=NotificationType.choices, default=NotificationType.NEWS)

    def is_visible(self):
        now = timezone.now()
        return self.is_active and (not self.expires_at or self.expires_at > now)

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"
    

class UserNotification(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    dismissed = models.BooleanField(default=False)
    seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'notification')

from django.db import models
from django.conf import settings

class StaffDocument(models.Model):
    DOCUMENT_TYPES = [
        ('resume', 'Resume'),
        ('certificate', 'Certificate'),
        ('id_card', 'ID Card'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    staff_profile = models.ForeignKey(
        'StaffProfile', 
        on_delete=models.CASCADE, 
        related_name='documents'
    )
    file = models.FileField(upload_to='staff_documents/')
    document_type = models.CharField(
        max_length=50, 
        choices=DOCUMENT_TYPES, 
        default='other'
    )
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} - {self.staff_profile.full_name} ({self.uploaded_at})"
    

class Event(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events')
    created_at = models.DateTimeField(auto_now_add=True)
    event_link = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.start_time} - {self.end_time})"

class EventParticipant(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    response = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')], default='pending')
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')

class PublicFolder(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subfolders')
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='public_folders')
    team = models.ForeignKey('Team', null=True, blank=True, on_delete=models.SET_NULL, related_name='public_folders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_public_folders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(department__isnull=False) | Q(team__isnull=False),
                name='public_folder_department_or_team_required'
            )
        ]

    def __str__(self):
        return self.name
    
def upload_to_public_folder(instance, filename):
    folder_name = instance.folder.name if instance.folder else "unassigned"
    return os.path.join('uploads/public', folder_name, filename)

class PublicFile(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_to_public_folder)
    folder = models.ForeignKey(PublicFolder, null=True, blank=True, on_delete=models.CASCADE, related_name='public_files')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_public_files')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.original_name