from django.core.mail import EmailMessage
import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from documents.forms import VacancyApplicationForm
from documents.models import Vacancy, VacancyApplication, CustomUser
from documents.viewfuncs.mail_connection import get_email_smtp_connection
from ..rba_decorators import is_hr
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.db.models import Count
from django.template.loader import render_to_string
from ..send_mails import send_vac_app_received_email, send_vac_app_accepted_email, send_vac_app_rejected_email


logger = logging.getLogger(__name__)

main_superuser = CustomUser.objects.filter(is_superuser=True).first()

SUPERUSER_EMAIL_PROVIDER = main_superuser.email_provider
SUPERUSER_EMAIL_ADDRESS = main_superuser.email_address
SUPERUSER_EMAIL_PASSWORD = main_superuser.get_smtp_password()

@login_required
@user_passes_test(is_hr)
def vacancy_application_list(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancies = Vacancy.objects.filter(tenant=request.tenant).annotate(app_count=Count('applications'))
    paginator = Paginator(vacancies, 10)  # 10 applications per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    return render(request, 'hr/vacancy_application_list.html', {'vacancies': page_obj})


def send_vacancy_application_received(request, application_id):
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy = vacancy_application.vacancy
    hrs = CustomUser.objects.filter(tenant=request.tenant, is_active=True, roles__name='HR')
    hr = hrs[0]
    sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
    sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
    sender_password = hr.email_password if hr.get_smtp_password() else SUPERUSER_EMAIL_PASSWORD
    candidate_name = vacancy_application.first_name
    company = vacancy_application.tenant.name

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    # Send application received email
    send_vac_app_received_email(sender_provider, sender_email, sender_password, company, candidate_name, vacancy_application, vacancy)
    
    print("Mail Sent")

def create_vacancy_application(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    if request.method == 'POST':
        form = VacancyApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            vacancy_application = form.save(commit=False)
            vacancy_application.vacancy = vacancy
            vacancy_application.tenant = request.tenant
            vacancy_application.save()
            send_vacancy_application_received(request, vacancy_application.id)
            return render(request, 'hr/vacancy_application_success.html', {'name':vacancy_application.first_name, 'vacancy': vacancy})
    else:
        form = VacancyApplicationForm()
    return render(request, 'hr/create_vacancy_application.html', {'form': form, 'vacancy': vacancy}) 

@login_required
@user_passes_test(is_hr)
def applications_per_vacancy(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    vacancy_applications = VacancyApplication.objects.filter(tenant=request.tenant, vacancy=vacancy)
    paginator = Paginator(vacancy_applications, 10)  # 10 applications per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    return render(request, 'hr/applications_per_vacancy.html', {'vacancy_applications': page_obj, 'vacancy': vacancy})

@login_required
@user_passes_test(is_hr)
def vacancy_application_detail(request, vacancy_id, application_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant, vacancy=vacancy)
    
    return render(request, 'hr/vacancy_application_detail.html', {'vacancy_application': vacancy_application})

@login_required
@user_passes_test(is_hr)
def delete_vacancy_application(request, vacancy_id, application_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant, vacancy=vacancy)
    vacancy_application.delete()
    return redirect('applications_per_vacancy', vacancy_id=vacancy_id)

def send_vacancy_accepted_mail(request, application_id):
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy = vacancy_application.vacancy
    hr = request.user
    if not is_hr(hr):
        print(f"Unauthorized access by user {request.user.username}. Only HRs can perform this action")
        return render(request, 'tenant_error.html', {'error_code': '403','message': 'Only HRs can perform this action.'})
    
    sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
    sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
    sender_password = hr.email_password if hr.get_smtp_password() else SUPERUSER_EMAIL_PASSWORD
    candidate_name = vacancy_application.first_name
    company = vacancy_application.tenant.name

    if hr.email_provider and hr.email_address and hr.email_password:
        cc = []
    else:
        cc = [hr.email]
    
    print("CC: ", cc)

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    # Send application accepted email
    send_vac_app_accepted_email(sender_provider, sender_email, sender_password, company, candidate_name, hr, cc, vacancy_application, vacancy)
    
    print("Mail Sent")

def send_vacancy_rejected_mail(request, application_id):
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy = vacancy_application.vacancy
    hr = request.user
    if not is_hr(hr):
        print(f"Unauthorized access by user {request.user.username}. Only HRs can perform this action")
        return render(request, 'tenant_error.html', {'error_code': '403','message': 'Only HRs can perform this action.'})
    
    sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
    sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
    sender_password = hr.email_password if hr.get_smtp_password() else SUPERUSER_EMAIL_PASSWORD
    candidate_name = vacancy_application.first_name.capitalize()
    company = vacancy_application.tenant.name

    if hr.email_provider and hr.email_address and hr.email_password:
        cc = []
    else:
        cc = [hr.email]
    
    print("CC: ", cc)

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    # Send application rejected email
    send_vac_app_rejected_email(sender_provider, sender_email, sender_password, company, candidate_name, hr, cc, vacancy_application, vacancy)
    
    print("Mail Sent")
    
# non-form accept, reject vacancy application
@login_required
@user_passes_test(is_hr)
def accept_vac_app(request, application_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy_application.status = 'accepted'
    vacancy_application.save()
    send_vacancy_accepted_mail(request, application_id)
    return redirect('vacancy_application_detail', vacancy_id=vacancy_application.vacancy.id, application_id=vacancy_application.id)

@login_required
@user_passes_test(is_hr)
def reject_vac_app(request, application_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy_application.status = 'rejected'
    vacancy_application.save()
    send_vacancy_rejected_mail(request, application_id)
    return redirect('vacancy_application_detail', vacancy_id=vacancy_application.vacancy.id, application_id=vacancy_application.id)

@login_required
@user_passes_test(is_hr)
def fetch_accepted_applications(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    applications = VacancyApplication.objects.filter(vacancy=vacancy, status='accepted')
    emails = []
    for app in applications:
        emails.append(app.email)
    paginator = Paginator(applications, 10)  # 10 applications per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'hr/accepted_applications.html', {'applications': page_obj, 'vacancy': vacancy, 'emails': emails})

@login_required
@user_passes_test(is_hr)
def fetch_rejected_applications(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    applications = VacancyApplication.objects.filter(vacancy=vacancy, status='rejected')
    emails = []
    for app in applications:
        emails.append(app.email)
    paginator = Paginator(applications, 10)  # 10 applications per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'hr/rejected_applications.html', {'applications': page_obj, 'vacancy': vacancy, 'emails': emails})