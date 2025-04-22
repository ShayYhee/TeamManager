from django import forms
from .models import Document, User, CustomUser

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
        fields = ["username", "email", "phone_number", "roles", "position"]
