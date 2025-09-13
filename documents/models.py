from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from raadaa import settings
from django.utils import timezone
import os, json, uuid
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet
from tenants.models import Tenant

# Generate or load encryption key for SMTP password
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
cipher = Fernet(ENCRYPTION_KEY)

def upload_to_documents_word(instance, filename):
    tenant_name = instance.tenant.name
    username = instance.created_by.username if instance.created_by else "anonymous"
    return os.path.join('documents', tenant_name, username, 'word', filename)

def upload_to_documents_pdf(instance, filename):
    tenant_name = instance.tenant.name
    username = instance.created_by.username if instance.created_by else "anonymous"
    return os.path.join('documents', tenant_name, username, 'pdf', filename)

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

    word_file = models.FileField(upload_to=upload_to_documents_word)
    pdf_file = models.FileField(upload_to=upload_to_documents_pdf, null=True, blank=True)
    # uploaded_file = models.FileField(upload_to='documents/', blank=True, null=True)

    document_source = models.CharField(max_length=20, choices=DOCUMENT_SOURCE_CHOICES, default='template')

    email_sent = models.BooleanField(default=False)  # Track if email was sent

    def __str__(self):
        return f"{self.document_type} - {self.company_name}"


from django.contrib.auth.models import AbstractUser
from django.db import models

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')

    def __str__(self):
        return self.name
    

class CustomUser(AbstractUser):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, blank=True, null=True, related_name="customuser")
    roles = models.ManyToManyField(Role, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    teams = models.ManyToManyField('Team', blank=True, related_name='members')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    zoho_email = models.EmailField(blank=True, null=True)
    zoho_password = models.CharField(max_length=255, blank=True, null=True)  # Encrypted SMTP password

    def set_smtp_password(self, password):
        """Encrypt and store SMTP password."""
        if password:
            self.zoho_password = cipher.encrypt(password.encode()).decode()
        else:
            self.zoho_password = None

    def get_smtp_password(self):
        """Decrypt and return SMTP password."""
        if self.zoho_password:
            return cipher.decrypt(self.zoho_password.encode()).decode()
        return None

    def clean(self):
        """Validate SMTP credentials."""
        if self.zoho_email and not self.zoho_password:
            raise ValidationError("Zoho password is required if Zoho email is provided. Necessary for email sending.")
        if self.zoho_password and not self.zoho_email:
            raise ValidationError("Zoho email is required if Zoho password is provided. Necessary for email sending.")

    def is_hod(self):
        return self.roles.filter(name='HOD').exists()

    def __str__(self):
        return self.username
    
    def has_perm(self, perm, obj=None):
        if obj and hasattr(obj, 'tenant'):
            if self.tenant != obj.tenant:
                return False
        return super().has_perm(perm, obj)


class Folder(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_shared = models.BooleanField(default=False, help_text="Enable external sharing for this folders.")
    shared_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='shared_folders')
    share_time = models.DateTimeField(null=True, blank=True)
    share_time_end = models.DateTimeField(null=True, blank=True)
    share_subfolders = models.BooleanField(default=False, null=True, blank=True)
    share_files = models.BooleanField(default=False, null=True, blank=True)

    def get_shareable_link(self):
        from django.urls import reverse
        return reverse('shared_folder_view', kwargs={'token': str(self.share_token)})

    def __str__(self):
        return self.name
    
def upload_to_folder(instance, filename):
    if instance.folder:
        tenant_name = instance.folder.tenant.name
        username = instance.folder.created_by.username if instance.folder.created_by else "anonymous"
        folder_name = instance.folder.name
        
        # Handle anonymous subdir
        if instance.anon_name or instance.anon_email or instance.anon_phone:
            subdir = instance.anon_name or instance.anon_email or instance.anon_phone.replace(' ', '_').replace('/', '_')[:50]  # Sanitize
        else:
            subdir = "anonymous_uploads"
        
        return os.path.join('uploads', tenant_name, username, folder_name, subdir, filename)
    elif instance.tenant:
        tenant_name = instance.tenant.name
        username = "anonymous"
        folder_name = "unassigned"
        return os.path.join('uploads', tenant_name, username, folder_name, filename)
    else:
        tenant_name = "unassigned"
        username = "anonymous"
        folder_name = "unassigned"
        return os.path.join('uploads', tenant_name, username, folder_name, filename)


class File(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='files', null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    anon_name = models.CharField(max_length=255, blank=True, null=True, help_text="Name of uploader if anonymous")
    anon_email = models.EmailField(blank=True, null=True, help_text="Email of uploader if anonymous")
    anon_phone = models.CharField(max_length=20, blank=True, null=True, help_text="Phone number of uploader if anonymous")
    file = models.FileField(upload_to=upload_to_folder)
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_shared = models.BooleanField(default=False, help_text="Enable external sharing for this file")
    shared_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='shared_files')
    share_time = models.DateTimeField(null=True, blank=True)
    share_time_end = models.DateTimeField(null=True, blank=True)

    def get_uploaded_by_display(self):
        if self.uploaded_by:
            return str(self.uploaded_by)
        elif self.anon_name:
            return self.anon_name
        return "Anonymous"

    def get_shareable_link(self):
        from django.urls import reverse
        return reverse('shared_file_view', kwargs={'token': str(self.share_token)})

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
    title = models.CharField(max_length=255, help_text="Required. Title of the task")
    description = models.TextField(help_text="Any notes or details about the task")
    documents = models.ManyToManyField('File', blank=True, help_text="Attach documents for this task from Public Files")
    assigned_to = models.ManyToManyField(settings.AUTH_USER_MODEL, null=True, blank=True, help_text="Select staff to assign this task to")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tasks')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', help_text="Current status of the task")
    due_date = models.DateField(null=True, blank=True, help_text="Set a due date for the task")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# class Organization(models.Model):
#     name = models.CharField(max_length=255, unique=True)

#     def __str__(self):
#         return self.name
    
class Department(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="department")
    name = models.CharField(max_length=255)
    hod = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='hod_department')

    def save(self, *args, **kwargs):
        if self.hod and not self.hod.is_hod():
            # raise ValueError("HOD must have the 'HOD' role.")
            self.hod.roles.add(Role.objects.get(name='HOD'))
            self.hod.save()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return self.name
    
class Team(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="team")
    name = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, blank=True, null=True)
    team_leader = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='team_leader')

    class Meta:
        unique_together = ('tenant', 'name')

    def __str__(self):
        return self.name
    
def upload_to_staff_photos(instance, filename):
    tenant_name = instance.tenant.name
    username = instance.user.username if instance.user.username else "anonymous"
    return os.path.join('staff_photos', tenant_name, username, filename)
    
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

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="staff_profile")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    photo = models.ImageField(upload_to=upload_to_staff_photos, null=True, blank=True)
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
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="notification")
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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.expires_at and self.expires_at < timezone.now():
            self.is_active = False
    

class UserNotification(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="user_notification")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    dismissed = models.BooleanField(default=False)
    seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'notification')


def upload_to_staff_documents(instance, filename):
    tenant_name = instance.tenant.name
    username = instance.staff_profile.user.username if instance.staff_profile.user else "anonymous"
    return os.path.join('staff_documents', tenant_name, username, filename)

class StaffDocument(models.Model):
    DOCUMENT_TYPES = [
        ('resume', 'Resume'),
        ('certificate', 'Certificate'),
        ('id_card', 'ID Card'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="staff_document")
    staff_profile = models.ForeignKey('StaffProfile', on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to=upload_to_staff_documents)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='other')
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

def upload_to_public_folder(instance, filename):
    folder_name = instance.folder.name if instance.folder else "unassigned"
    return os.path.join('uploads/public', folder_name, filename)

def upload_to_company_photos(instance, filename):
    tenant_name = instance.tenant.name
    return os.path.join('company_photos', tenant_name, filename)

class CompanyProfile(models.Model):
    photo = models.ImageField(upload_to=upload_to_company_photos, null=True, blank=True)
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="company_profile")
    company_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    date_founded = models.DateField(null=True, blank=True)
    reg_number = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    contact_details = models.TextField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    num_staff = models.IntegerField(null=True, blank=True)
    num_departments = models.IntegerField(null=True, blank=True)
    num_teams = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.tenant.name
    

class Contact(models.Model):
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    organization = models.CharField(max_length=255, null=True, blank=True)
    designation = models.CharField(max_length=255, blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.SET_NULL, related_name='contact_lists')
    team = models.ForeignKey('Team', null=True, blank=True, on_delete=models.SET_NULL, related_name='contact_lists')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_contact_lists')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_contact_lists', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.email})"
    # class Meta:
    #     constraints = [
    #         models.CheckConstraint(
    #             check=Q(department__isnull=False) | Q(team__isnull=False),
    #             name='contact_list_department_or_team_required'
    #         )
    #     ]

class Email(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    to_emails = models.TextField()  # Store email addresses as JSON
    cc_emails = models.TextField(blank=True)  # Optional
    bcc_emails = models.TextField(blank=True)  # Optional
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sender_email')
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def set_to_emails(self, emails):
        """Helper to store list of emails as JSON."""
        self.to_emails = json.dumps(emails)

    def get_to_emails(self):
        """Helper to retrieve list of emails."""
        return json.loads(self.to_emails) if self.to_emails else []

    def set_cc_emails(self, emails):
        self.cc_emails = json.dumps(emails)

    def get_cc_emails(self):
        return json.loads(self.cc_emails) if self.cc_emails else []

    def set_bcc_emails(self, emails):
        self.bcc_emails = json.dumps(emails)

    def get_bcc_emails(self):
        return json.loads(self.bcc_emails) if self.bcc_emails else []

    def __str__(self):
        return self.subject

# class Email(models.Model):
#     tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
#     subject = models.CharField(max_length=255)
#     body = models.TextField()
#     to = models.ManyToManyField(Contact, blank=False, related_name='recipients')
#     cc = models.ManyToManyField(Contact, blank=True, related_name='copy_recipients')
#     bcc = models.ManyToManyField(Contact, blank=True, related_name='blind_recipients')
#     sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sender_email')
#     created_at = models.DateTimeField(auto_now_add=True)
#     sent = models.BooleanField(default=False)
#     sent_at = models.DateTimeField(null=True, blank=True)

def upload_to_email_attachments(instance, filename):
    tenant_name = instance.email.tenant.name
    username = instance.email.sender.username if instance.email.sender.username else "anonymous"
    return os.path.join('email_attachments', tenant_name, username, filename)

class Attachment(models.Model):
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=upload_to_email_attachments)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
    
class Payee(models.Model):
    PAYEE_TYPE_CHOICES = [
        ('employee', 'Employee'),  # Internal, linked to CustomUser
        ('contractor', 'Contractor'),  # External, freelance or temporary
        ('vendor', 'Vendor'),  # External, for suppliers or services
        ('other', 'Other'),  # Catch-all for miscellaneous
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payees')
    user = models.OneToOneField(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='payee_profile')  # Link to internal user if applicable
    payee_type = models.CharField(max_length=20, choices=PAYEE_TYPE_CHOICES, default='employee')
    name = models.CharField(max_length=255)  # Full name or company name
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)  # For tax/compliance purposes
    tax_id = models.CharField(max_length=50, blank=True, null=True)  # e.g., SSN, EIN for US; adaptable for other countries
    account_number = models.CharField(max_length=100, blank=True, null=True)  # IBAN, account number, etc.
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_name = models.CharField(max_length=100, blank=True, null=True)
    routing_number = models.CharField(max_length=50, blank=True, null=True)  # For bank transfers
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.payee_type}) for {self.tenant}"

    def save(self, *args, **kwargs):
        if self.user:
            # Auto-populate from CustomUser if linked
            self.name = self.user.get_full_name() or self.user.username
            self.email = self.user.email
            self.payee_type = 'employee'
            self.account_number = self.user.staff_profile.account_number
            self.bank_name = self.user.staff_profile.bank_name
            self.account_name = self.user.staff_profile.account_name
        super().save(*args, **kwargs)

class Payroll(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('processed', 'Processed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payrolls')
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)  # Sum of all linked payments
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_payrolls')

    def __str__(self):
        return f"Payroll for {self.tenant} ({self.period_start} to {self.period_end})"

    # def save(self, *args, **kwargs):
    #     super().save(*args, **kwargs)
    #     # Optionally auto-calculate total_amount from linked payments
    #     self.total_amount = sum(payment.amount for payment in self.payments.all()) or 0
    #     super().save(*args, **kwargs)  # Save again to update total

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payroll_payments')
    payee = models.ForeignKey(Payee, on_delete=models.CASCADE, related_name='payments')  # Links to Payee (internal or external)
    payroll = models.ForeignKey(Payroll, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')  # Optional link to Payroll for batching
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # After deductions
    tax_deductions = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    payroll_period_start = models.DateField(null=True, blank=True)
    payroll_period_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)  # From payment gateway or bank
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # e.g., 'bank_transfer', 'direct_deposit'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment of {self.amount} to {self.payee} by {self.tenant}"
    
def upload_to_company_documents(instance, filename):
    tenant_name = instance.tenant.name
    return os.path.join('company_documents', tenant_name, filename)

class CompanyDocument(models.Model):
    DOCUMENT_TYPES = [
        ('certificate', 'Certificate'),
        ('contract', 'Contract'),
        ('license', 'License'),
        ('memorandum', 'Memorandum'),
        ('other', 'Other'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="company_document")
    company_profile = models.ForeignKey('CompanyProfile', on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to=upload_to_company_documents)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='other')
    description = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} - {self.company_profile.full_name} ({self.uploaded_at})"