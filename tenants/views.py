from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponseForbidden
from .models import Tenant, TenantApplication
from .forms import TenantApplicationForm
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
            form.save()
        else:
            logger.error(f"Tenant application form validation failed: {form.errors}")
        # return redirect('check_status')
    else:
        form = TenantApplicationForm()
    return render(request, 'tenants/apply_for_tenant.html', {'form': form})

def check_status(request):
    return render(request, 'tenants/check_status.html')

# @login_required
def application_status(request, username):
    applications = TenantApplication.objects.filter(username=username)
    logger.debug(f"Listed {applications.count()} applications for user: {request.user.username}")
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