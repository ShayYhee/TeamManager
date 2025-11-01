# Authentication
# Custom Login, Login Redirects, Forgot password, and more

from raadaa import settings
from documents.models import CustomUser, StaffProfile
from documents.forms import ForgotPasswordForm, SignUpForm, CustomLoginForm
from django.contrib.auth import logout, get_user_model, update_session_auth_hash
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.views import LoginView
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from .send_mails import send_reg_confirm, send_password_reset_email
from .mail_connection import get_email_smtp_connection
from django.contrib.auth.forms import SetPasswordForm


User = get_user_model()

# User account registration
def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.username = form.cleaned_data["email"]
            user.set_password(form.cleaned_data["password"])
            # user.is_active = False
            user.is_active = True
            user.tenant = request.tenant
            if not request.tenant:
                return HttpResponseForbidden("No company associated with this request.")
            user.save()
            try:
                created = StaffProfile.objects.create(tenant=user.tenant, user=user)
                created.first_name = form.cleaned_data["first_name"]
                created.last_name = form.cleaned_data["last_name"]
                created.email = form.cleaned_data["email"]
                created.save()
            except ValidationError as e:
                print(f"Staff Profile creation error: {e}")
                return redirect('view_my_profile')
            
             # Send confirmation email
            admin_user = CustomUser.objects.filter(
                tenant=request.tenant, roles__name="Admin"
            ).first()
            superuser = CustomUser.objects.filter(is_superuser=True).first()
            send_reg_confirm(request, user, admin_user, superuser)

            # Log error or notify admin, but proceed with registration
            return redirect("account_activation_sent")
    else:
        form = SignUpForm()
    return render(request, "registration/register.html", {"form": form})

# account activation 
def account_activation_sent(request):
    return render(request, "registration/account_activation_sent.html")

# Custom Login
# class CustomLoginView(LoginView):
#     def form_valid(self, form):
#         # Authenticate and log in the user
#         response = super().form_valid(form)  # Logs in the user
#         user = self.request.user

#         # If superuser, allow staying on base domain
#         if user.is_superuser:
#             return response

#         # For non-superusers, redirect to their tenant's login URL
#         expected_subdomain = (
#             user.tenant.slug
#             if hasattr(user, 'tenant') and user.tenant
#             else None
#         )
#         if expected_subdomain is None:
#             return HttpResponseForbidden("You are not associated with this company. Please ensure your subdomain is correct or contact faith.osebi@transnetcloud.com")
#         base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
#         protocol = "http" if settings.DEBUG else "https"
#         tenant_login_url = f"{protocol}://{expected_subdomain}.{base_domain}/accounts/login"

#         # Redirect to tenant-specific login URL
#         return redirect(tenant_login_url)

#     def get(self, request, *args, **kwargs):
#         # If already authenticated, redirect to home or tenant URL
#         if request.user.is_authenticated:
#             if request.user.is_superuser:
#                 return redirect(settings.LOGIN_REDIRECT_URL or '/')
#             expected_subdomain = (
#                 request.user.tenant.slug
#                 if hasattr(request.user, 'tenant') and request.user.tenant
#                 else None
#             )
#             if expected_subdomain is None:
#                 return HttpResponseForbidden("You are not associated with this company. Please ensure your subdomain is correct or contact faith.osebi@transnetcloud.com")
#             base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
#             protocol = "http" if settings.DEBUG else "https"
#             return redirect(f"{protocol}://{expected_subdomain}.{base_domain}/")
#         return super().get(request, *args, **kwargs)


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'registration/login.html'  # Make sure to use your template

    def form_valid(self, form):
        # The rest of your existing logic remains the same
        response = super().form_valid(form)
        user = self.request.user

        if user.is_superuser:
            return response

        expected_subdomain = (
            user.tenant.slug
            if hasattr(user, 'tenant') and user.tenant
            else None
        )
        if expected_subdomain is None:
            return HttpResponseForbidden("You are not associated with this company. Please ensure your subdomain is correct or contact faith.osebi@transnetcloud.com")
        
        base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
        protocol = "http" if settings.DEBUG else "https"
        tenant_login_url = f"{protocol}://{expected_subdomain}.{base_domain}/accounts/login"

        return redirect(tenant_login_url)

    def get(self, request, *args, **kwargs):
        # Your existing get method logic remains the same
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return redirect(settings.LOGIN_REDIRECT_URL or '/')
            expected_subdomain = (
                request.user.tenant.slug
                if hasattr(request.user, 'tenant') and request.user.tenant
                else None
            )
            if expected_subdomain is None:
                return HttpResponseForbidden("You are not associated with this company. Please ensure your subdomain is correct or contact faith.osebi@transnetcloud.com")
            base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
            protocol = "http" if settings.DEBUG else "https"
            return redirect(f"{protocol}://{expected_subdomain}.{base_domain}/")
        return super().get(request, *args, **kwargs)


# Fetch Tenant URL for redirecting users
def get_tenant_url(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        if not CustomUser.objects.filter(id=request.user.id, tenant=request.tenant).exists():
            print(f"User {request.user.username} not associated with tenant {request.tenant.slug if request.tenant else 'None'}")
            expected_subdomain = (
                request.user.tenant.slug
                if hasattr(request.user, 'tenant') and request.user.tenant
                else None
            )
            if expected_subdomain is None:
                logout(request)
                raise PermissionDenied("You have no associated tenant. Contact support. faith.osebi@transnetcloud.com")
            print(f"Wrong user tenant slug: {expected_subdomain}")
            base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
            protocol = "http" if settings.DEBUG else "https"
            home_url = f"{protocol}://{expected_subdomain}.{base_domain}/"
            print(f"Redirecting to tenant home: {home_url}")
            return home_url
    
# Forgot password view
def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            # form.save(commit=False)
            email = form.cleaned_data['email']
            user = CustomUser.objects.get(email=email)
            # Generate token and UID
            token = default_token_generator.make_token(user)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            # Build reset URL
            reset_url = request.build_absolute_uri(
                reverse('reset_password', kwargs={'uidb64': uidb64, 'token': token})
            )
            superuser = CustomUser.objects.get(is_superuser=True)
            send_password_reset_email(user, reset_url, superuser)
            return redirect('password_reset_sent')  # Or a 'email sent' page if you want to add one
    else:
        form = ForgotPasswordForm()
    return render(request, 'registration/forgot_password.html', {'form': form})

# Reset password view
# def reset_password(request, uidb64, token):
#     try:
#         uid = force_str(urlsafe_base64_decode(uidb64))
#         user = User.objects.get(pk=uid)
#     except (TypeError, ValueError, OverflowError, User.DoesNotExist):
#         user = None

#     if user and default_token_generator.check_token(user, token):
#         if request.method == 'POST':
#             form = ResetPasswordForm(user, request.POST)
#             if form.is_valid():
#                 form.save()
#                 return redirect('password_reset_success')
#         else:
#             form = ResetPasswordForm(user)
#         return render(request, 'registration/reset_password.html', {'form': form})
#     else:
#         # Invalid link (expired or tampered)
#         return render(request, 'registration/reset_password.html', {'error': 'Invalid or expired reset link.'})



def reset_password(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Check if user exists and token is valid
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                # Update session auth hash if user is logged in
                update_session_auth_hash(request, form.user)
                return redirect('password_reset_success')
        else:
            form = SetPasswordForm(user)
        
        context = {
            'form': form,
            'validlink': True
        }
        return render(request, 'registration/reset_password.html', context)
    else:
        # Invalid link
        context = {
            'form': None,
            'validlink': False,
            'error': 'Invalid or expired password reset link. Please request a new one.'
        }
        return render(request, 'registration/reset_password.html', context)

def password_reset_success(request):
    return render(request, 'registration/password_reset_success.html')


# Password reset sent view
def password_reset_sent(request):
    return render(request, 'registration/password_reset_sent.html')

# Post login redirect
def post_login_redirect(request):
    if not request.user.is_authenticated or request.user.is_superuser:
        return redirect('tenant_home')
    return redirect('home')

# Home page
def home(request):
    tenant = request.tenant
    print("This is home")
    return render(request, "home.html", {'tenant': tenant})