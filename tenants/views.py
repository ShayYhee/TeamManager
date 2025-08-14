from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail, get_connection
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from .models import Tenant, TenantApplication
from .forms import TenantApplicationForm, TenantForm
from documents.models import CustomUser, Role, Department, Team, StaffProfile, CompanyProfile, Contact, Email, Event
from django.contrib.auth import authenticate, login
from django.db.models import Q, Count
import logging
from raadaa import settings

logger = logging.getLogger(__name__)

def home(request):
    return render(request, 'tenant_home.html')

def apply_for_tenant(request):
    if request.method == 'POST':
        form = TenantApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.status = 'approved'
            application.save()
            
            try:
                # tenant_admin = CustomUser.objects.get(username=application.username)
                tenant = Tenant.objects.create(
                    name=application.organization_name,
                    slug=application.slug
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
                user.save()
                tenant.admin = user
                tenant.save()
                application.status = 'approved'
                application.save()
                logger.debug(f"Assigned Admin role to user {tenant.admin.username} for tenant {tenant.slug}")
                # Login redirect
                base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
                protocol = "http" if settings.DEBUG else "https"
                login_url = f"{protocol}://{application.slug}.{base_domain}/accounts/login"
                # return redirect('login')
                return render(request, 'tenants/login_redirect.html', {'login_url': login_url})
            except Exception as e:
                logger.error(f"Error creating tenant for application {application.organization_name}: {str(e)}")
                return HttpResponseForbidden(f"Error creating tenant: {str(e)}")
            # Generate status URL
            # status_url = request.build_absolute_uri(
            #     redirect('application_status', identifier=str(application.id)).url
            # )
            # # Send email
            # superadmin = CustomUser.objects.get(is_superuser=True)
            # email = superadmin.zoho_email
            # password = superadmin.zoho_password
            # connection = get_connection(
            #     backend="django.core.mail.backends.smtp.EmailBackend",
            #     host="smtp.zoho.com",
            #     port=587,
            #     username=email,
            #     password=password,
            #     use_tls=True,
            # )
            # try:
            #     send_mail(
            #         subject='Your Tenant Application Status',
            #         message=(
            #             f"Thank you for applying to Team Manager!\n\n"
            #             f"Check your application status here: {status_url}\n\n"
            #             f"Keep this link safe, as you'll need it to track your application."
            #         ),
            #         connection=connection,
            #         recipient_list=[form.cleaned_data['email']],
            #         fail_silently=False,
            #     )
            #     messages.success(request, "Application submitted successfully! A status link has been sent to your email.")
            # except Exception as e:
            #     logger.error(f"Failed to send email: {e}")
            #     messages.warning(request, "Application submitted, but we couldn't send the status link email. Please check your status manually.")
            # return redirect('application_status', identifier=str(application.id))
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

def delete_tenant_app(request, tenant_application_id):
    tenant_app = get_object_or_404(TenantApplication, id=tenant_application_id)
    tenant_app.delete()
    return redirect('tenant_applications')

@login_required
def tenant_list(request):
    if request.user.is_superuser:
        tenants = Tenant.objects.all()
    else:
        tenants = Tenant.objects.filter(
            Q(created_by=request.user) | Q(admin=request.user) | Q(customuser__id=request.user.id)
        ).distinct()
    logger.debug(f"Listed {tenants.count()} tenants for user: {request.user.username}")

    count = tenants.count()

    for tenant in tenants:
        tenant.num_users = CustomUser.objects.filter(tenant=tenant).count()

    paginator = Paginator(tenants, 10)  # 10 users per page
    page_number = request.GET.get('page')
    tenants = paginator.get_page(page_number)
    return render(request, 'tenants/tenant_list.html', {'tenants': tenants, 'count':count})

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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def verify_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    tenant.is_verified = True
    tenant.save()
    return redirect('tenant_list')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def users_list(request):
    users = CustomUser.objects.all()
    paginator = Paginator(users, 10)  # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    count = users.count()
    return render(request, "tenants/users_list.html", {"users": page_obj, 'count': count})

# @login_required
# @user_passes_test(lambda u: u.is_superuser)
# def superuser_dashboard(request):
#     tenants = Tenant.objects.all()
#     users = CustomUser.objects.all()
#     tenants_app = TenantApplication.objects.all()
#     depts = Department.objects.all()
#     teams = Team.objects.all()
#     roles = Role.objects.all()
#     staff_prof = StaffProfile.objects.all()
#     comp_prof = CompanyProfile.objects.all()
#     events = Event.objects.all()
#     contacts = Contact.objects.all()
#     emails = Email.objects.all()

#     context = {
#         'tenants':tenants, 'users': users, 'tenants_app': tenants_app, 'depts': depts, 'teams': teams, 'roles': roles,
#         'staff_prof': staff_prof, 'comp_prof': comp_prof, 'events': events, 'contacts': contacts, 'emails': emails,
#     }
#     return render(request, 'tenants/dashboard.html', context)
    
@login_required
@user_passes_test(lambda u: u.is_superuser)
def superuser_dashboard(request):
    # Annotate with distinct counts to avoid duplicates from joins
    tenants = Tenant.objects.annotate(
        user_count=Count('customuser', distinct=True),  # Use distinct to count unique users
        dept_count=Count('department', distinct=True),  # Use distinct for departments
        team_count=Count('team', distinct=True),       # Use distinct for teams
    ).all()

    # If annotations still produce incorrect counts, compute separately as a fallback
    tenant_data = []
    for tenant in tenants:
        tenant_data.append({
            'name': tenant.name,  # Adjust to your Tenant field (e.g., tenant.slug or str(tenant))
            'slug': tenant.slug,
            'user_count': CustomUser.objects.filter(tenant=tenant).count(),
            'dept_count': Department.objects.filter(tenant=tenant).count(),
            'team_count': Team.objects.filter(tenant=tenant).count(),
        })

    users = CustomUser.objects.all()
    tenants_app = TenantApplication.objects.all()
    depts = Department.objects.all()
    teams = Team.objects.all()
    roles = Role.objects.all()
    staff_prof = StaffProfile.objects.all()
    comp_prof = CompanyProfile.objects.all()
    events = Event.objects.all()
    contacts = Contact.objects.all()
    emails = Email.objects.all()

    # Prepare chart data using tenant_data for reliability
    tenant_names = [tenant['name'] for tenant in tenant_data]
    user_counts = [tenant['user_count'] for tenant in tenant_data]
    dept_counts = [tenant['dept_count'] for tenant in tenant_data]
    team_counts = [tenant['team_count'] for tenant in tenant_data]

    context = {
        'tenants': tenants,
        'users': users,
        'tenants_app': tenants_app,
        'depts': depts,
        'teams': teams,
        'roles': roles,
        'staff_prof': staff_prof,
        'comp_prof': comp_prof,
        'events': events,
        'contacts': contacts,
        'emails': emails,
        'tenant_names': tenant_names,
        'user_counts': user_counts,
        'dept_counts': dept_counts,
        'team_counts': team_counts,
    }
    return render(request, 'tenants/dashboard.html', context)