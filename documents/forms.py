from django import forms
from django.forms import modelformset_factory
from .models import Document, User, CustomUser, Folder, File, Task, StaffProfile, StaffDocument, Department, Team, PublicFolder, PublicFile, Role, Event, EventParticipant, Notification, UserNotification, CompanyProfile, Contact, Email, Attachment, CompanyDocument
from tenants.models import Tenant
from ckeditor.widgets import CKEditorWidget
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.contrib.auth import get_user_model
import json

User = get_user_model()

class TenantAwareModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

def filter_by_tenant(queryset, user):
    tenant = getattr(user, 'tenant', None)
    if tenant:
        return queryset.filter(tenant=tenant)
    return queryset.none()


class DocumentForm(forms.ModelForm):
    creation_method = forms.ChoiceField(
        choices=[('template', 'Use Template'), ('upload', 'Upload Document')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    uploaded_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.docx,.pdf'}),
        help_text='Upload a .docx or .pdf file (required if using Upload Document option)'
    )
    document_type = forms.ChoiceField(
        choices=[('approval', 'Approval Letter'), ('sla', 'SLA Document')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False  # Not required for uploaded documents
    )

    class Meta:
        model = Document
        fields = [
            'creation_method',
            'uploaded_file',
            'document_type',
            'company_name',
            'company_address',
            'contact_person_name',
            'contact_person_email',
            'contact_person_designation',
            'sales_rep'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_person_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_person_designation': forms.TextInput(attrs={'class': 'form-control'}),
            'sales_rep': forms.TextInput(attrs={'class': 'form-control sales-rep-field'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        creation_method = cleaned_data.get('creation_method')
        uploaded_file = cleaned_data.get('uploaded_file')
        document_type = cleaned_data.get('document_type')

        if creation_method == 'upload':
            if not uploaded_file:
                raise forms.ValidationError('You must upload a .docx or .pdf file when using the Upload Document option.')
            if not uploaded_file.name.lower().endswith(('.docx', '.pdf')):
                raise forms.ValidationError('Only .docx or .pdf files are allowed.')
            # if document_type:
            #     self.add_error('document_type', 'Document type should not be selected when uploading a document.')
            # Set document_type to 'Uploaded' for uploads
            cleaned_data['document_type'] = 'Uploaded'
        else:
            if not document_type:
                raise forms.ValidationError('Document type is required when using a template.')
            if uploaded_file:
                self.add_error('uploaded_file', 'Do not upload a file when using a template.')

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Ensure document_type is set to 'Uploaded' for upload method
        if self.cleaned_data['creation_method'] == 'upload':
            instance.document_type = 'Uploaded'
        if commit:
            instance.save()
        return instance

class CreateDocumentForm(forms.Form):
    title = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Document Title'})
    )
    content = forms.CharField(
        widget=CKEditorUploadingWidget(config_name='custom_toolbar'),
        required=True
    )
    
class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "password"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match")
        if not first_name:
            raise forms.ValidationError("Please Enter First Name")
        if not last_name:
            raise forms.ValidationError("Please Enter Last Name")
        return cleaned_data
    
class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))
    class Meta:
        model = CustomUser
        fields = ['username', 'password', 'password_confirm', 'first_name', 'last_name', 'email', 
                  'is_active', 'roles', 'phone_number', 
                  'department', 'teams', 'zoho_email', 'zoho_password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password_confirm': forms.PasswordInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'roles': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'teams': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'zoho_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'zoho_password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'password': 'Choose a strong password',
            'password_confirm': 'Confirm your password',
            'zoho_email': 'Enter your Zoho email address',
            'zoho_password': 'Enter your Zoho password',
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['department'].queryset = Department.objects.filter(tenant=tenant)
            self.fields['teams'].queryset = Team.objects.filter(tenant=tenant)
        else:
            self.fields['department'].queryset = Department.objects.none()
            self.fields['teams'].queryset = Team.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class EditUserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 
                  'is_active', 'roles', 'phone_number', 
                  'department', 'teams']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'roles': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'teams': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['department'].queryset = Department.objects.filter(tenant=tenant)
            self.fields['teams'].queryset = Team.objects.filter(tenant=tenant)
        else:
            self.fields['department'].queryset = Department.objects.none()
            self.fields['teams'].queryset = Team.objects.none()

class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent': forms.HiddenInput(),
            # 'parent': forms.ModelChoiceField(queryset=Folder.objects.all(), required=False, widget=forms.HiddenInput),
        }

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['folder', 'file']
        widgets = {
            'folder': forms.HiddenInput(),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'documents', 'assigned_to', 'due_date', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'documents': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'assigned_to': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['assigned_to'].queryset = CustomUser.objects.filter(tenant=tenant)
                self.fields['documents'].queryset = PublicFile.objects.filter(tenant=tenant, created_by=user)
            else:
                self.fields['assigned_to'].queryset = CustomUser.objects.none()
                self.fields['documents'].queryset = PublicFile.objects.none()

class ReassignTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['assigned_to', 'due_date']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'},)
        }
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['assigned_to'].queryset = filter_by_tenant(CustomUser.objects.all(), user)

class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = StaffProfile
        fields = [
            "photo",
            "first_name", "last_name", "middle_name", "email", "phone_number", "sex", "date_of_birth", "home_address",
            "state_of_origin", "lga", "religion",
            "institution", "course", "degree", "graduation_year",
            "account_number", "bank_name", "account_name",
            "location", "employment_date", "department", "team", "designation", "official_email",
            "emergency_name", "emergency_relationship", "emergency_phone",
            "emergency_address", "emergency_email",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "graduation_year": forms.DateInput(attrs={"type": "date"}),
            "employment_date": forms.DateInput(attrs={"type": "date"}),
            "home_address": forms.Textarea(attrs={"rows": 2}),
            "emergency_address": forms.Textarea(attrs={"rows": 2}),
            "team": forms.SelectMultiple(attrs={"class": "form-control"}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['department'].queryset = Department.objects.filter(tenant=tenant)
                self.fields['team'].queryset = Team.objects.filter(tenant=tenant)
            else:
                self.fields['department'].queryset = Department.objects.none()
                self.fields['team'].queryset = Team.objects.none
        
class StaffDocumentForm(forms.ModelForm):
    class Meta:
        model = StaffDocument
        fields = ['file', 'document_type', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and file.size > 5 * 1024 * 1024:  # 5MB limit
            raise forms.ValidationError("File size must be under 5MB.")
        return file
    
class EmailConfigForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['zoho_email', 'zoho_password' ]
        widgets = {
            'zoho_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'zoho_password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

class PublicFolderForm(forms.ModelForm):
    class Meta:
        model = PublicFolder
        fields = ['name', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent': forms.HiddenInput(),
        }

class PublicFileForm(forms.ModelForm):
    class Meta:
        model = PublicFile
        fields = ['file']

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'hod']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'hod': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # tenant = getattr(user, 'tenant', None)
            tenant = user.tenant
            if tenant:
                self.fields['hod'].queryset = CustomUser.objects.filter(tenant=tenant)
            else:
                self.fields['hod'].queryset = CustomUser.objects.none()

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'department', 'team_leader']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-control'}),
            'team_leader': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['department'].queryset = Department.objects.filter(tenant=tenant)
                self.fields['team_leader'].queryset = CustomUser.objects.filter(tenant=tenant)
            else:
                self.fields['department'].queryset = Department.objects.none()
                self.fields['team_leader'].queryset = CustomUser.objects.none()

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'description', 'start_time', 'end_time', 'event_link']
        widgets = {
            "start_time": forms.DateInput(attrs={'type': 'date', 'class': 'form-control'},),
            "end_time": forms.DateInput(attrs={'type': 'date', 'class': 'form-control'},),
            "description": forms.Textarea(attrs={"rows": 2}),
            "link": forms.URLInput(attrs={"class": 'form-control'}),
        }

class EventParticipantForm(forms.ModelForm):
    
    class Meta:
        model = EventParticipant
        fields = ['event', 'user', 'response']
        widgets = {
            'event': forms.Select(attrs={'class': 'form-control'}),
            'user': forms.Select(attrs={'class': 'form-control'}),
            'response': forms.Select(attrs={'class': 'form-control'}, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')]),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['event'].queryset = Event.objects.filter(tenant=tenant)
                self.fields['user'].queryset = CustomUser.objects.filter(tenant=tenant)
            else:
                self.fields['department'].queryset = CustomUser.objects.none()
                self.fields['team'].queryset = Department.objects.none

class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'message', 'type', 'expires_at']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control'}, choices=Notification.NotificationType),
            'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

class UserNotificationForm(forms.ModelForm):
    class Meta:
        model = UserNotification
        fields = ['user', 'notification']
        widgets = {
            'user': forms.Select(attrs={'class': 'form-control'}),
            'notification': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['user'].queryset = CustomUser.objects.filter(tenant=tenant)
                self.fields['notification'].queryset = Notification.objects.filter(tenant=tenant)
            else:
                self.fields['user'].queryset = CustomUser.objects.none()
                self.fields['notification'].queryset = Notification.objects.none()

class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ['photo', 'company_name',  'description', 'date_founded', 'reg_number', 
                  'address', 'email', 'contact_details', 'website']
        widgets = {
            'description' : forms.TextInput(attrs={'rows': 5, 'class': 'form-control'}),
            'date_founded': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contact_details': forms.TextInput(attrs={'rows': 4, 'class': 'form-control'})
        }

class CompanyDocumentForm(forms.ModelForm):
    class Meta:
        model = CompanyDocument
        fields = ['file', 'document_type', 'description']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and file.size > 10 * 1024 * 1024:  # 10MB limit
            raise forms.ValidationError("File size must be under 10MB.")
        return file

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'email', 'phone', 'organization', 'designation', 'priority', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'organization': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# class EmailForm(forms.ModelForm):
#     class Meta:
#         model = Email
#         fields = ['subject', 'body', 'to', 'cc', 'bcc']
#         widgets = {
#             'subject': forms.TextInput(attrs={'class': 'form-control'}),
#             'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
#             'to': forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': 'multiple'}),
#             'cc': forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': 'multiple'}),
#             'bcc': forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': 'multiple'}),
#         }

#     def __init__(self, *args, **kwargs):
#         user = kwargs.pop('user', None)
#         super().__init__(*args, **kwargs)
#         if user:
#             tenant = getattr(user, 'tenant', None)
#             if tenant:
#                 self.fields['to'].queryset = Contact.objects.filter(tenant=tenant, department=user.department)
#                 self.fields['cc'].queryset = Contact.objects.filter(tenant=tenant, department=user.department)
#                 self.fields['bcc'].queryset = Contact.objects.filter(tenant=tenant, department=user.department)
#             else:
#                 self.fields['to'].queryset = Contact.objects.none()
#                 self.fields['cc'].queryset = Contact.objects.none()
#                 self.fields['bcc'].queryset = Contact.objects.none()

class EmailForm(forms.ModelForm):
    to_emails = forms.CharField(
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Enter emails or select contacts',
            'data-tags': 'true',
            'data-token-separators': '[",", " "]'
        }),
        help_text="Enter email addresses or select contacts, separated by commas or spaces.",
        required=True
    )
    cc_emails = forms.CharField(
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Enter CC emails or select contacts',
            'data-tags': 'true',
            'data-token-separators': '[",", " "]'
        }),
        help_text="Enter CC email addresses or select contacts, separated by commas or spaces.",
        required=False
    )
    bcc_emails = forms.CharField(
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Enter BCC emails or select contacts',
            'data-tags': 'true',
            'data-token-separators': '[",", " "]'
        }),
        help_text="Enter BCC email addresses or select contacts, separated by commas or spaces.",
        required=False
    )
    attachments = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control'
        }),
        required=False
    )

    class Meta:
        model = Email
        fields = ['subject', 'body', 'to_emails', 'cc_emails', 'bcc_emails']

    def clean_to_emails(self):
        """Validate and process to_emails field."""
        emails = self.cleaned_data['to_emails']
        print(f"To Emails: {emails}")
        email_list = []
        if isinstance(emails, str):
            try:
                # Handle stringified list (e.g., "['email1','email2']")
                parsed_emails = json.loads(emails.replace("'", '"'))
                email_list = [email.strip() for email in parsed_emails if email.strip()]
                print(f"To Emails string instance: {email_list}")
            except (json.JSONDecodeError, TypeError):
                # Handle comma-separated string
                email_list = [email.strip() for email in emails.split(',') if email.strip()]
        else:
            # Handle list input from SelectMultiple
            email_list = [email.strip() for email in emails if email.strip()]
            print(f"To Emails list instance: {email_list}")
        if not email_list:
            raise forms.ValidationError("At least one recipient email is required.")
        for email in email_list:
            if not self._is_valid_email(email):
                raise forms.ValidationError(f"Invalid email address: {email}")
        return email_list

    def clean_cc_emails(self):
        """Validate and process cc_emails field."""
        emails = self.cleaned_data['cc_emails']
        email_list = []
        if isinstance(emails, str):
            try:
                parsed_emails = json.loads(emails.replace("'", '"'))
                email_list = [email.strip() for email in parsed_emails if email.strip()]
            except (json.JSONDecodeError, TypeError):
                email_list = [email.strip() for email in emails.split(',') if email.strip()]
        else:
            email_list = [email.strip() for email in emails if email.strip()]
        for email in email_list:
            if not self._is_valid_email(email):
                raise forms.ValidationError(f"Invalid email address: {email}")
        return email_list

    def clean_bcc_emails(self):
        """Validate and process bcc_emails field."""
        emails = self.cleaned_data['bcc_emails']
        email_list = []
        if isinstance(emails, str):
            try:
                parsed_emails = json.loads(emails.replace("'", '"'))
                email_list = [email.strip() for email in parsed_emails if email.strip()]
            except (json.JSONDecodeError, TypeError):
                email_list = [email.strip() for email in emails.split(',') if email.strip()]
        else:
            email_list = [email.strip() for email in emails if email.strip()]
        for email in email_list:
            if not self._is_valid_email(email):
                raise forms.ValidationError(f"Invalid email address: {email}")
        return email_list
    
    def clean_attachments(self):
        """Validate multiple file attachments."""
        files = self.files.getlist('attachments')
        if not files:
            return None
        for f in files:
            if f.size > 10 * 1024 * 1024:  # 10MB limit
                raise forms.ValidationError(f"File {f.name} is too large (max 10MB).")
        return files

    def _is_valid_email(self, email):
        """Validate email format."""
        from django.core.validators import validate_email
        try:
            validate_email(email)
            return True
        except forms.ValidationError:
            return False

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.set_to_emails(self.cleaned_data['to_emails'])
        instance.set_cc_emails(self.cleaned_data['cc_emails'])
        instance.set_bcc_emails(self.cleaned_data['bcc_emails'])
        if commit:
            instance.save()
            # Save attachments
            files = self.cleaned_data.get('attachments')
            if files:
                for f in files:
                    Attachment.objects.create(email=instance, file=f)
        return instance

    
# Formset for attachments
# AttachmentFormSet = modelformset_factory(
#     Attachment,
#     fields=('file',),
#     extra=3,  # Allow up to 3 additional attachments
#     can_delete=True,
#     widgets={'file': forms.FileInput(attrs={'class': 'form-control'})}
# )

class SupportForm(forms.Form):
    subject = forms.CharField(max_length=255, required=True)
    message = forms.CharField(widget=forms.Textarea, required=True)
    attachments = forms.FileField(
        widget=forms.FileInput(attrs={'class':'form-control'}),
        required=False
    )

    def clean_attachments(self):
        files = self.files.getlist('attachments')
        print("Cleaning attachments: %s", [(f.name, f.size, f.content_type) for f in files])
        if not files:
            print("No attachments provided")
            return None
        for f in files:
            if f.size > 10 * 1024 * 1024:  # 10MB limit
                raise forms.ValidationError(f"File {f.name} is too large (max 10MB).")
            if f.content_type not in ['image/jpeg', 'image/png']:
                raise forms.ValidationError(f"File {f.name} is not a valid JPG/PNG file.")
        return files