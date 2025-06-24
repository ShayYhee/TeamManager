from django import forms
from django.forms import modelformset_factory
from .models import Document, User, CustomUser, Folder, File, Task, StaffProfile, StaffDocument, Department, Team, PublicFolder, PublicFile
from ckeditor.widgets import CKEditorWidget
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.contrib.auth import get_user_model

User = get_user_model()

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
        fields = '__all__'


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

class ReassignTaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['assigned_to', 'due_date']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'},)
        }

class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = StaffProfile
        fields = [
            "photo",
            "first_name", "last_name", "middle_name", "email", "phone_number", "sex", "date_of_birth", "home_address",
            "state_of_origin", "lga", "religion",
            "institution", "course", "degree", "graduation_year",
            "account_number", "bank_name", "account_name",
            "location", "employment_date",
            "organization", "department", "team", "designation", "official_email",
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
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        label='Department'
    )
    team = forms.ModelChoiceField(
        queryset=Team.objects.all(),
        required=False,
        label='Team'
    )

    class Meta:
        model = PublicFolder
        fields = ['name', 'parent', 'department', 'team']

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