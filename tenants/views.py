from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.core.mail import send_mail, get_connection
from django.core.management import call_command
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.utils import timezone
from .models import Tenant, TenantApplication
from .forms import TenantApplicationForm, TenantForm
from documents.models import CustomUser, Role, Department, Team, StaffProfile, CompanyProfile, Contact, Email, Event, Task, Folder, File, Vacancy, VacancyApplication
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
            # email = superadmin.email_address
            # password = superadmin.email_password
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
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
    if request.user.is_superuser or request.user.tenant.slug == 'track':
        tenant_apps = TenantApplication.objects.all()
    else:
        HttpResponseForbidden(f'You are not authorized to view this')
    return render(request, 'tenants/tenant_applications.html', {'tenants': tenant_apps})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_tenant_app(request, tenant_application_id):
    tenant_app = get_object_or_404(TenantApplication, id=tenant_application_id)
    tenant_app.delete()
    return redirect('tenant_applications')

@login_required
def tenant_list(request):
    if request.user.is_superuser or request.user.tenant.slug == 'track':
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
@user_passes_test(lambda u: u.is_superuser or u.tenant.slug == 'track')
def users_list(request):
    users = CustomUser.objects.all()
    paginator = Paginator(users, 10)  # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    count = users.count()
    return render(request, "tenants/users_list.html", {"users": page_obj, 'count': count})
    
@login_required
@user_passes_test(lambda u: u.is_superuser or u.tenant.slug == 'track')
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

def get_user_data():
    # get all unexpired sessions
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    
    user_ids = []
    for session in sessions:
        data = session.get_decoded()
        user_id = data.get('_auth_user_id')
        if user_id:
            user_ids.append(user_id)
    
    # Get all users tied to active sessions
    active_users = CustomUser.objects.filter(id__in=user_ids)
    
    # Count totals
    total_active_users = active_users.count()
    
    # Aggregate per tenant
    active_users_per_tenant = list(
        active_users.values('tenant__id', 'tenant__name')
        .annotate(active_user_count=Count('id'))
        .order_by('-active_user_count')[:20]
    )
    
    return {
        'total_active_users': total_active_users,
        'active_users_per_tenant': active_users_per_tenant,
    }
    
# Tracking
@login_required
@user_passes_test(lambda u: u.is_superuser or u.tenant.slug == 'track')
def tracking_dashboard(request):
    # Task metrics (from task_dashboard logic)
    total_tasks = Task.objects.count()
    tasks_per_tenant = list(
        Task.objects.values('tenant__id', 'tenant__name')
        .annotate(task_count=Count('id'))
        .order_by('-task_count')[:20]
    )
    top_task_tenant_ids = [item['tenant__id'] for item in tasks_per_tenant]
    task_general_status_counts = list(
        Task.objects.values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )
    task_status_per_tenant = list(
        Task.objects.filter(tenant__id__in=top_task_tenant_ids)
        .values('tenant__id', 'tenant__name', 'status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # Folder/File metrics (from folder_file_dashboard logic)
    total_folders = Folder.objects.count()
    folders_per_tenant = list(
        Folder.objects.values('tenant__id', 'tenant__name')
        .annotate(folder_count=Count('id'))
        .order_by('-folder_count')[:20]
    )
    total_shared_folders = Folder.objects.filter(is_shared=True).count()
    shared_folders_per_tenant = list(
        Folder.objects.filter(is_shared=True)
        .values('tenant__id', 'tenant__name')
        .annotate(shared_folder_count=Count('id'))
        .order_by('-shared_folder_count')[:20]
    )
    total_files = File.objects.count()
    files_per_tenant = list(
        File.objects.values('tenant__id', 'tenant__name')
        .annotate(file_count=Count('id'))
        .order_by('-file_count')[:20]
    )
    total_shared_files = File.objects.filter(is_shared=True).count()
    shared_files_per_tenant = list(
        File.objects.filter(is_shared=True)
        .values('tenant__id', 'tenant__name')
        .annotate(shared_file_count=Count('id'))
        .order_by('-shared_file_count')[:20]
    )
    general_folder_shared = [{'shared': 'Shared', 'count': total_shared_folders}, {'shared': 'Non-Shared', 'count': total_folders - total_shared_folders}]
    general_file_shared = [{'shared': 'Shared', 'count': total_shared_files}, {'shared': 'Non-Shared', 'count': total_files - total_shared_files}]

    # Vacancy/Application metrics (from vacancy_dashboard logic)
    total_vacancies = Vacancy.objects.count()
    vacancies_per_tenant = list(
        Vacancy.objects.values('tenant__id', 'tenant__name')
        .annotate(vacancy_count=Count('id'))
        .order_by('-vacancy_count')[:20]
    )
    total_shared_vacancies = Vacancy.objects.filter(is_shared=True).count()
    shared_vacancies_per_tenant = list(
        Vacancy.objects.filter(is_shared=True)
        .values('tenant__id', 'tenant__name')
        .annotate(shared_vacancy_count=Count('id'))
        .order_by('-shared_vacancy_count')[:20]
    )
    general_work_mode_counts = list(
        Vacancy.objects.values('work_mode')
        .annotate(count=Count('id'))
        .order_by('work_mode')
    )
    work_mode_per_tenant = list(
        Vacancy.objects.values('tenant__id', 'tenant__name', 'work_mode')
        .annotate(count=Count('id'))
        .order_by('tenant__id', 'work_mode')
    )
    general_status_counts = list(
        Vacancy.objects.values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )
    status_per_tenant = list(
        Vacancy.objects.values('tenant__id', 'tenant__name', 'status')
        .annotate(count=Count('id'))
        .order_by('tenant__id', 'status')
    )
    total_applications = VacancyApplication.objects.count()
    applications_per_tenant = list(
        VacancyApplication.objects.values('tenant__id', 'tenant__name')
        .annotate(application_count=Count('id'))
        .order_by('-application_count')[:20]
    )
    accepted_count = VacancyApplication.objects.filter(status='accepted').count()
    rejected_count = VacancyApplication.objects.filter(status='rejected').count()
    pending_count = VacancyApplication.objects.filter(Q(status__isnull=True) | Q(status='')).count()
    general_app_status_counts = [
        {'status': 'accepted', 'count': accepted_count},
        {'status': 'rejected', 'count': rejected_count},
        {'status': 'pending', 'count': pending_count},
    ]
    accepted_per_tenant = list(VacancyApplication.objects.filter(status='accepted').values('tenant__id', 'tenant__name').annotate(count=Count('id')))
    for item in accepted_per_tenant:
        item['status'] = 'accepted'
    rejected_per_tenant = list(VacancyApplication.objects.filter(status='rejected').values('tenant__id', 'tenant__name').annotate(count=Count('id')))
    for item in rejected_per_tenant:
        item['status'] = 'rejected'
    pending_per_tenant = list(VacancyApplication.objects.filter(Q(status__isnull=True) | Q(status='')).values('tenant__id', 'tenant__name').annotate(count=Count('id')))
    for item in pending_per_tenant:
        item['status'] = 'pending'
    app_status_per_tenant = accepted_per_tenant + rejected_per_tenant + pending_per_tenant
    general_vacancy_shared = [{'shared': 'Shared', 'count': total_shared_vacancies}, {'shared': 'Non-Shared', 'count': total_vacancies - total_shared_vacancies}]
    # Top 20 vacancies by application count
    top_vacancies_by_applications = list(
        VacancyApplication.objects.values('vacancy__id', 'vacancy__title', 'tenant__name')
        .annotate(application_count=Count('id'))
        .order_by('-application_count')[:20]
    )

    # User stats
    user_context = get_user_data()

    context = {
        # Task keys
        'total_tasks': total_tasks,
        'tasks_per_tenant': tasks_per_tenant,
        'task_general_status_counts': task_general_status_counts,
        'task_status_per_tenant': task_status_per_tenant,
        # Folder/File keys
        'total_folders': total_folders,
        'folders_per_tenant': folders_per_tenant,
        'total_shared_folders': total_shared_folders,
        'shared_folders_per_tenant': shared_folders_per_tenant,
        'total_files': total_files,
        'files_per_tenant': files_per_tenant,
        'total_shared_files': total_shared_files,
        'shared_files_per_tenant': shared_files_per_tenant,
        'general_folder_shared': general_folder_shared,
        'general_file_shared': general_file_shared,
        # Vacancy/Application keys
        'total_vacancies': total_vacancies,
        'vacancies_per_tenant': vacancies_per_tenant,
        'total_shared_vacancies': total_shared_vacancies,
        'shared_vacancies_per_tenant': shared_vacancies_per_tenant,
        'general_work_mode_counts': general_work_mode_counts,
        'work_mode_per_tenant': work_mode_per_tenant,
        'general_status_counts': general_status_counts,  # Note: This key is shared with tasks; prefix if conflicts
        'status_per_tenant': status_per_tenant,  # Note: Shared key; prefix if conflicts
        'total_applications': total_applications,
        'applications_per_tenant': applications_per_tenant,
        'general_app_status_counts': general_app_status_counts,
        'app_status_per_tenant': app_status_per_tenant,
        'general_vacancy_shared': general_vacancy_shared,
        'top_vacancies_by_applications': top_vacancies_by_applications,
        # User keys
        'total_active_users': user_context['total_active_users'],
        'active_users_per_tenant': user_context['active_users_per_tenant'],
    }

    return render(request, 'tracking/dashboard.html', context)

@login_required
def track_user(request):
    context = get_user_data()
    return render(request, 'tracking/loggedin_users_dashboard.html', context)

@login_required
def track_tasks(request):
    # Total number of tasks (general tasks)
    total_tasks = Task.objects.count()

    # Number of tasks per tenant
    tasks_per_tenant = list(Task.objects.values('tenant__id', 'tenant__name').annotate(task_count=Count('id')).order_by('tenant__id'))

    # General status counts (across all tasks)
    general_status_counts = list(Task.objects.values('status').annotate(count=Count('id')).order_by('status'))

    # Status counts per tenant
    status_per_tenant = list(Task.objects.values('tenant__id', 'tenant__name', 'status').annotate(count=Count('id')).order_by('tenant__id', 'status'))

    context = {
        'total_tasks': total_tasks,
        'tasks_per_tenant': tasks_per_tenant,
        'task_general_status_counts': general_status_counts,
        'task_status_per_tenant': status_per_tenant,
    }

    return render(request, 'tracking/tasks_dashboard.html', context)

@login_required
def track_folder_file(request):
    # Folder metrics
    total_folders = Folder.objects.count()
    # Top 20 tenants by folder count
    folders_per_tenant = list(
        Folder.objects.values('tenant__id', 'tenant__name')  # Adjust 'tenant__name' if your Tenant model has a different field for name/display
            .annotate(folder_count=Count('id'))
            .order_by('-folder_count')[:20]
    )
    top_folder_tenant_ids = [item['tenant__id'] for item in folders_per_tenant]

    total_shared_folders = Folder.objects.filter(is_shared=True).count()
    # Shared folders per tenant, filtered to top 20 by shared count
    shared_folders_per_tenant = list(
        Folder.objects.filter(is_shared=True)
            .values('tenant__id', 'tenant__name')
            .annotate(shared_folder_count=Count('id'))
            .order_by('-shared_folder_count')[:20]
    )

    # File metrics
    total_files = File.objects.count()
    # Top 20 tenants by file count
    files_per_tenant = list(
        File.objects.values('tenant__id', 'tenant__name')  # Adjust 'tenant__name' as needed
            .annotate(file_count=Count('id'))
            .order_by('-file_count')[:20]
    )
    top_file_tenant_ids = [item['tenant__id'] for item in files_per_tenant]

    total_shared_files = File.objects.filter(is_shared=True).count()
    # Shared files per tenant, filtered to top 20 by shared count
    shared_files_per_tenant = list(
        File.objects.filter(is_shared=True)
            .values('tenant__id', 'tenant__name')
            .annotate(shared_file_count=Count('id'))
            .order_by('-shared_file_count')[:20]
    )

    # For general shared vs non-shared (for pie charts)
    general_folder_shared = [{'shared': 'Shared', 'count': total_shared_folders}, {'shared': 'Non-Shared', 'count': total_folders - total_shared_folders}]
    general_file_shared = [{'shared': 'Shared', 'count': total_shared_files}, {'shared': 'Non-Shared', 'count': total_files - total_shared_files}]

    context = {
        'total_folders': total_folders,
        'folders_per_tenant': folders_per_tenant,
        'total_shared_folders': total_shared_folders,
        'shared_folders_per_tenant': shared_folders_per_tenant,
        'total_files': total_files,
        'files_per_tenant': files_per_tenant,
        'total_shared_files': total_shared_files,
        'shared_files_per_tenant': shared_files_per_tenant,
        'general_folder_shared': general_folder_shared,
        'general_file_shared': general_file_shared,
    }

    return render(request, 'tracking/folder_file_dashboard.html', context)

@login_required
def track_vacancy(request):
    # Vacancy metrics
    total_vacancies = Vacancy.objects.count()
    # Top 20 tenants by vacancy count
    vacancies_per_tenant = list(
        Vacancy.objects.values('tenant__id', 'tenant__name')
            .annotate(vacancy_count=Count('id'))
            .order_by('-vacancy_count')[:20]
    )
    top_vacancy_tenant_ids = [item['tenant__id'] for item in vacancies_per_tenant]

    total_shared_vacancies = Vacancy.objects.filter(is_shared=True).count()
    # Top 20 tenants by shared vacancy count
    shared_vacancies_per_tenant = list(
        Vacancy.objects.filter(is_shared=True)
            .values('tenant__id', 'tenant__name')
            .annotate(shared_vacancy_count=Count('id'))
            .order_by('-shared_vacancy_count')[:20]
    )

    # Work mode counts (general)
    general_work_mode_counts = list(
        Vacancy.objects.values('work_mode')
            .annotate(count=Count('id'))
            .order_by('work_mode')
    )

    # Work mode counts per tenant (all tenants, will slice in JS to top 20 if needed)
    work_mode_per_tenant = list(
        Vacancy.objects.values('tenant__id', 'tenant__name', 'work_mode')
            .annotate(count=Count('id'))
            .order_by('tenant__id', 'work_mode')
    )

    # Status counts (general)
    general_status_counts = list(
        Vacancy.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('status')
    )

    # Status counts per tenant (all tenants, will slice in JS)
    status_per_tenant = list(
        Vacancy.objects.values('tenant__id', 'tenant__name', 'status')
            .annotate(count=Count('id'))
            .order_by('tenant__id', 'status')
    )

    # VacancyApplication metrics
    total_applications = VacancyApplication.objects.count()

    # Top 20 tenants by application count
    applications_per_tenant = list(
        VacancyApplication.objects.values('tenant__id', 'tenant__name')
            .annotate(application_count=Count('id'))
            .order_by('-application_count')[:20]
    )

    # General app status counts with pending combined
    accepted_count = VacancyApplication.objects.filter(status='accepted').count()
    rejected_count = VacancyApplication.objects.filter(status='rejected').count()
    pending_count = VacancyApplication.objects.filter(Q(status__isnull=True) | Q(status='')).count()
    general_app_status_counts = [
        {'status': 'accepted', 'count': accepted_count},
        {'status': 'rejected', 'count': rejected_count},
        {'status': 'pending', 'count': pending_count},
    ]

    # App status per tenant with explicit status
    accepted_per_tenant = list(
        VacancyApplication.objects.filter(status='accepted')
            .values('tenant__id', 'tenant__name')
            .annotate(count=Count('id'))
    )
    for item in accepted_per_tenant:
        item['status'] = 'accepted'

    rejected_per_tenant = list(
        VacancyApplication.objects.filter(status='rejected')
            .values('tenant__id', 'tenant__name')
            .annotate(count=Count('id'))
    )
    for item in rejected_per_tenant:
        item['status'] = 'rejected'

    pending_per_tenant = list(
        VacancyApplication.objects.filter(Q(status__isnull=True) | Q(status=''))
            .values('tenant__id', 'tenant__name')
            .annotate(count=Count('id'))
    )
    for item in pending_per_tenant:
        item['status'] = 'pending'

    app_status_per_tenant = accepted_per_tenant + rejected_per_tenant + pending_per_tenant

    # For general shared vs non-shared vacancies
    general_vacancy_shared = [{'shared': 'Shared', 'count': total_shared_vacancies}, {'shared': 'Non-Shared', 'count': total_vacancies - total_shared_vacancies}]

    # Top 20 vacancies by application count
    top_vacancies_by_applications = list(
        VacancyApplication.objects.values('vacancy__id', 'vacancy__title', 'tenant__name')
        .annotate(application_count=Count('id'))
        .order_by('-application_count')[:20]
    )

    context = {
        'total_vacancies': total_vacancies,
        'vacancies_per_tenant': vacancies_per_tenant,
        'total_shared_vacancies': total_shared_vacancies,
        'shared_vacancies_per_tenant': shared_vacancies_per_tenant,
        'general_work_mode_counts': general_work_mode_counts,
        'work_mode_per_tenant': work_mode_per_tenant,
        'general_status_counts': general_status_counts,
        'status_per_tenant': status_per_tenant,
        'total_applications': total_applications,
        'applications_per_tenant': applications_per_tenant,
        'general_app_status_counts': general_app_status_counts,
        'app_status_per_tenant': app_status_per_tenant,
        'general_vacancy_shared': general_vacancy_shared,
        'top_vacancies_by_applications': top_vacancies_by_applications,
    }

    return render(request, 'tracking/vacancy_dashboard.html', context)