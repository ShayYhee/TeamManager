from django import forms
from django.forms import modelformset_factory
from .models import Document, User, CustomUser, Folder, File, Task, StaffProfile, StaffDocument, Department, Team, PublicFolder, PublicFile, Role, Event, EventParticipant, Notification, UserNotification
from tenants.models import Tenant
from ckeditor.widgets import CKEditorWidget
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.contrib.auth import get_user_model

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
        fields = ["username", "email", "password"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data
    
class UserForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 
                  'is_staff', 'is_active', 'roles', 'phone_number', 
                  'department', 'teams', 'smtp_email', 'smtp_password']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'roles': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'teams': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'smtp_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'smtp_password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['roles'].queryset = Role.objects.filter(tenant=tenant)
                self.fields['department'].queryset = Department.objects.filter(tenant=tenant)
                self.fields['teams'].queryset = Team.objects.filter(tenant=tenant)
            else:
                self.fields['roles'].queryset = Role.objects.none()
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
        fields = ['title', 'description', 'documents', 'folder', 'assigned_to', 'due_date', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'documents': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'folder': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
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
                self.fields['documents'].queryset = File.objects.filter(tenant=tenant, uploaded_by=user)
                self.fields['folder'].queryset = Folder.objects.filter(tenant=tenant, created_by=user)
            else:
                self.fields['assigned_to'].queryset = CustomUser.objects.none()
                self.fields['documents'].queryset = File.objects.none()
                self.fields['folder'].queryset = Folder.objects.none()

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
        fields = ['smtp_email', 'smtp_password' ]
        widgets = {
            'smtp_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'smtp_password': forms.PasswordInput(attrs={'class': 'form-control'}),
        }

class PublicFolderForm(forms.ModelForm):
    class Meta:
        model = PublicFolder
        fields = ['name', 'parent', 'department', 'team']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-control'}),
            'team': forms.Select(attrs={'class': 'form-control'}),
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

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        team = cleaned_data.get('team')
        parent = cleaned_data.get('parent')

        if not (department or team):
            raise forms.ValidationError('A public folder must be associated with a department or team.')
        if team and not department:
            raise forms.ValidationError('A team must be associated with a department.')
        if parent and team and parent.team != team:
            raise forms.ValidationError('Subfolder team must match parent team.')
        if parent and department and parent.department != department:
            raise forms.ValidationError('Subfolder department must match parent department.')

        return cleaned_data

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
        fields = ['name', 'department']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            tenant = getattr(user, 'tenant', None)
            if tenant:
                self.fields['department'].queryset = Department.objects.filter(tenant=tenant)
            else:
                self.fields['department'].queryset = Department.objects.none()

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