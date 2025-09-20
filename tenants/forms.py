from django import forms
from .models import TenantApplication, Tenant
from documents.models import CustomUser

class TenantApplicationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = TenantApplication
        fields = ['username', 'email', 'password', 'confirm_password', 'organization_name', 'slug']

    def clean_username(self):
        username = self.cleaned_data['username']
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

    def clean_organization_name(self):
        name = self.cleaned_data['organization_name']
        if TenantApplication.objects.filter(organization_name=name).exists() or Tenant.objects.filter(name=name).exists():
            raise forms.ValidationError("This organization name is already in use.")
        return name

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if TenantApplication.objects.filter(slug=slug).exists() or Tenant.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This slug is already in use.")
        if "_" in slug:
            raise forms.ValidationError("Slug cannot contain underscores. Use hyphens instead.")
        if slug.isnumeric():
            raise forms.ValidationError("Slug cannot be numeric. Start with a letter.")
        if len(slug) > 20:
            raise forms.ValidationError("Slug must be under 20 characters.")
        return slug.lower()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data
    

class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['name', 'slug', 'admin']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'admin': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['admin'].queryset = CustomUser.objects.filter(roles__name='Admin')