from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail, get_connection
from django.core.management import call_command
from django.http import HttpResponseForbidden
from .models import Tenant, TenantApplication
from .forms import TenantApplicationForm, TenantForm
from documents.models import CustomUser, Role
from django.contrib.auth import authenticate, login
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'tenant_home.html')

def apply_for_tenant(request):
    if request.method == 'POST':
        form = TenantApplicationForm(request.POST)
        if form.is_valid():
            application = form.save()
            # Generate status URL
            status_url = request.build_absolute_uri(
                redirect('application_status', identifier=str(application.id)).url
            )
            # Send email
            superadmin = CustomUser.objects.get(is_superuser=True)
            email = superadmin.smtp_email
            password = superadmin.smtp_password
            connection = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host="smtp.zoho.com",
                port=587,
                username=email,
                password=password,
                use_tls=True,
            )
            try:
                send_mail(
                    subject='Your Tenant Application Status',
                    message=(
                        f"Thank you for applying to Team Manager!\n\n"
                        f"Check your application status here: {status_url}\n\n"
                        f"Keep this link safe, as you'll need it to track your application."
                    ),
                    connection=connection,
                    recipient_list=[form.cleaned_data['email']],
                    fail_silently=False,
                )
                messages.success(request, "Application submitted successfully! A status link has been sent to your email.")
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                messages.warning(request, "Application submitted, but we couldn't send the status link email. Please check your status manually.")
            return redirect('application_status', identifier=str(application.id))
        else:
            logger.error(f"Tenant application form validation failed: {form.errors}")
            messages.error(request, "Application submission failed. Please correct the errors below.")
    else:
        form = TenantApplicationForm()
    return render(request, 'tenants/apply_for_tenant.html', {'form': form})

def check_status(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            application = TenantApplication.objects.get(email=email)
            return redirect('application_status', identifier=str(application.id))
        except TenantApplication.DoesNotExist:
            messages.error(request, "No application found for the provided email.")
    return render(request, 'tenants/check_status.html')

# @login_required
def application_status(request, identifier):
    applications = TenantApplication.objects.filter(id=identifier)
    logger.debug(f"Listed {applications.count()} applications for identifier: {identifier}")
    if not applications:
        messages.warning(request, "No applications found for the provided identifier.")
    return render(request, 'tenants/application_status.html', {'applications': applications})

@login_required
def create_tenant(request, tenant_application_id):
    if not request.user.is_superuser:
        logger.warning(f"Unauthorized tenant creation attempt by user: {request.user.username}")
        return HttpResponseForbidden("You are not authorized to create a tenant.")
    
    try:
        application = TenantApplication.objects.get(id=tenant_application_id, status='pending')
    except TenantApplication.DoesNotExist:
        logger.error(f"Tenant application {tenant_application_id} not found or not pending")
        return HttpResponseForbidden("Invalid or non-pending application.")
    
    try:
        # tenant_admin = CustomUser.objects.get(username=application.username)
        tenant = Tenant.objects.create(
            name=application.organization_name,
            slug=application.slug,
            created_by=request.user
        )
        tenant.save()
        user = CustomUser.objects.create_user(
                username=application.username,
                email=application.email,
                password=application.password,
                tenant=tenant
        )
        user.save()
        logger.info(f"Created tenant: {tenant.slug}")
        admin_role, _ = Role.objects.get_or_create(name='Admin')
        logger.info(f"Tenant application created: {application.organization_name} by {application.username}")
        user.roles.add(admin_role)
        user.set_password = application.password
        user.is_active = True
        user.is_staff = True
        user.save()
        tenant.admin = user
        tenant.save()
        application.status = 'approved'
        application.save()
        logger.debug(f"Assigned Admin role to user {tenant.admin.username} for tenant {tenant.slug}")
        return redirect('tenant_applications')
    except Exception as e:
        logger.error(f"Error creating tenant for application {application.organization_name}: {str(e)}")
        return HttpResponseForbidden(f"Error creating tenant: {str(e)}")
    
def reject_tenant(request, tenant_application_id):
    if not request.user.is_superuser:
        logger.warning(f"Unauthorized tenant rejection attempt by user: {request.user.username}")
        return HttpResponseForbidden("You are not authorized to reject a tenant.")
    
    try:
        tenant_app = TenantApplication.objects.get(id=tenant_application_id, status='pending')
        tenant_app.status = 'rejected'
        tenant_app.save()
    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_application_id} not found")
        return HttpResponseForbidden("Invalid tenant.")
    
    
    logger.info(f"Rejected tenant: {tenant_app.slug}")
    return redirect('tenant_list')
    
@login_required
def tenant_applications(request):
    if request.user.is_superuser:
        tenant_apps = TenantApplication.objects.all()
    else:
        HttpResponseForbidden(f'You are not authorized to view this')
    return render(request, 'tenants/tenant_applications.html', {'tenants': tenant_apps})

@login_required
def tenant_list(request):
    if request.user.is_superuser:
        tenants = Tenant.objects.all()
    else:
        tenants = Tenant.objects.filter(
            Q(created_by=request.user) | Q(admin=request.user) | Q(customuser__id=request.user.id)
        ).distinct()
    logger.debug(f"Listed {tenants.count()} tenants for user: {request.user.username}")
    return render(request, 'tenants/tenant_list.html', {'tenants': tenants})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    if request.method == 'POST':
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            return redirect('tenant_list')
    else:
        form = TenantForm(instance=tenant)
    return render(request, 'tenants/edit_tenant.html', {'form': form, 'tenant': tenant})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    tenant.delete()
    return redirect('tenant_list')