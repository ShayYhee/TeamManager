from django.core.mail import EmailMessage
import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from Raadaa.documents.forms import VacancyApplicationForm
from Raadaa.documents.models import Vacancy, VacancyApplication, CustomUser
from Raadaa.documents.viewfuncs.mail_connection import get_email_smtp_connection
from rba_decorators import is_hr
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.db.models import Count
from django.template.loader import render_to_string


logger = logging.getLogger(__name__)

main_superuser = CustomUser.objects.filter(is_superuser=True).first()

SUPERUSER_EMAIL_PROVIDER = main_superuser.email_provider
SUPERUSER_EMAIL_ADDRESS = main_superuser.email_address
SUPERUSER_EMAIL_PASSWORD = main_superuser.email_password

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


# def send_vacancy_application_received(request, application_id):
#     vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
#     vacancy = vacancy_application.vacancy
#     users = CustomUser.objects.filter(tenant=request.tenant, is_active=True)
#     hrs=[]
#     for user in users:
#         if is_hr(user):
#             hrs.append(user)
#     hr = hrs[0]
#     sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
#     sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
#     sender_password = hr.email_password if hr.email_password else SUPERUSER_EMAIL_PASSWORD
#     candidate_name = vacancy_application.first_name
#     company = vacancy_application.tenant.name


#     if not sender_email or not sender_password:
#         return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     subject = f"Application Received for {vacancy.title} Role"
#     message = f"""
#     Dear {candidate_name},

#     You have successfully applied for the {vacancy.title} position at {company}.

#     You will receive an email once the hiring manager reviews your application.

#     Please be sure to keep a close eye on your email inbox (including your spam or promotions folder) so you don't miss our message.

#     Best regards,

#     Human Resouces Team, 
#     {company}
#     """

#     print("Sending mail...")

#     # Create email with attachment
#     email = EmailMessage(subject, message, sender_email, [vacancy_application.email], connection=connection)
#     email.send()
    
#     print("Mail Sent")


def send_vacancy_application_received(request, application_id):
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy = vacancy_application.vacancy
    users = CustomUser.objects.filter(tenant=request.tenant, is_active=True)
    hrs = []
    for user in users:
        if is_hr(user):
            hrs.append(user)
    hr = hrs[0]
    sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
    sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
    sender_password = hr.email_password if hr.email_password else SUPERUSER_EMAIL_PASSWORD
    candidate_name = vacancy_application.first_name
    company = vacancy_application.tenant.name

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    # Prepare context for the template
    context = {
        'candidate_name': candidate_name,
        'vacancy_title': vacancy.title,
        'company_name': company,
        'application_date': vacancy_application.created_at.strftime('%B %d, %Y'),
    }

    # Render HTML content
    html_content = render_to_string('emails/application_received.html', context)

    subject = f"Application Received for {vacancy.title} Role"

    print("Sending mail...")

    # Create and send HTML email
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender_email,
        to=[vacancy_application.email],
        connection=connection
    )
    
    # Specify that this is HTML email
    email.content_subtype = "html"
    
    email.send()
    
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

# def send_vacancy_accepted_mail(request, application_id):
#     vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
#     vacancy = vacancy_application.vacancy
#     hr = request.user
#     if not is_hr(hr):
#         print(f"Unauthorized access by user {request.user.username}. Only HRs can perform this action")
#         return render(request, 'tenant_error.html', {'error_code': '403','message': 'Only HRs can perform this action.'})
#     sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
#     sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
#     sender_password = hr.email_password if hr.email_password else SUPERUSER_EMAIL_PASSWORD
#     candidate_name = vacancy_application.first_name
#     company = vacancy_application.tenant

#     if hr.email_provider and hr.email_address and hr.email_password:
#         cc = []
#     else:
#         cc = [hr.email]
    
#     print("CC: ", cc)

#     if not sender_email or not sender_password:
#         return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     subject = f"You're Moving Forward! Next Steps for the {vacancy.title} Role"
#     message = f"""
#     Dear {candidate_name},

#     Congratulations! Thank you for your application for the {vacancy.title} position at {company}. We were thoroughly impressed with your background, and we are excited to inform you that you have been selected to move forward in our hiring process!

#     Your next step is to stay tuned. Our team is currently coordinating the next phase, and you will be receiving a follow-up email from us shortly with detailed instructions.

#     Please be sure to keep a close eye on your email inbox (including your spam or promotions folder) so you don't miss our message.

#     We are very much looking forward to connecting with you soon and learning more about how you could contribute to our team at {company}.

#     If you have any immediate questions, please feel free to reply to this email.

#     Best regards,

#     Human Resouces Team, 
#     {company}
#     {hr.email}
#     """

#     print("Sending mail...")

#     # Create email with attachment
#     email = EmailMessage(subject=subject, body=message, from_email=sender_email, to=[vacancy_application.email], cc=cc, connection=connection)
#     email.send()
    
#     print("Mail Sent")


def send_vacancy_accepted_mail(request, application_id):
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy = vacancy_application.vacancy
    hr = request.user
    if not is_hr(hr):
        print(f"Unauthorized access by user {request.user.username}. Only HRs can perform this action")
        return render(request, 'tenant_error.html', {'error_code': '403','message': 'Only HRs can perform this action.'})
    
    sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
    sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
    sender_password = hr.email_password if hr.email_password else SUPERUSER_EMAIL_PASSWORD
    candidate_name = vacancy_application.first_name
    company = vacancy_application.tenant.name

    if hr.email_provider and hr.email_address and hr.email_password:
        cc = []
    else:
        cc = [hr.email]
    
    print("CC: ", cc)

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    # Prepare context for the template
    context = {
        'candidate_name': candidate_name,
        'vacancy_title': vacancy.title,
        'company_name': company,
        'hr_email': hr.email,
        'hr_name': hr.get_full_name() or hr.username,
    }

    # Render HTML content
    html_content = render_to_string('emails/application_accepted.html', context)

    subject = f"You're Moving Forward! Next Steps for the {vacancy.title} Role"

    print("Sending mail...")

    # Create and send HTML email
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender_email,
        to=[vacancy_application.email],
        cc=cc,
        connection=connection
    )
    
    # Specify that this is HTML email
    email.content_subtype = "html"
    
    email.send()
    
    print("Mail Sent")


# def send_vacancy_rejected_mail(request, application_id):
#     vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
#     vacancy = vacancy_application.vacancy
#     hr = request.user
#     if not is_hr(hr):
#         print(f"Unauthorized access by user {request.user.username}. Only HRs can perform this action")
#         return render(request, 'tenant_error.html', {'error_code': '403','message': 'Only HRs can perform this action.'})
    
#     sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
#     sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
#     sender_password = hr.email_password if hr.email_password else SUPERUSER_EMAIL_PASSWORD
#     candidate_name = vacancy_application.first_name.capitalize()
#     company = vacancy_application.tenant.name

#     if hr.email_provider and hr.email_address and hr.email_password:
#         cc = []
#     else:
#         cc = [hr.email]
    
#     print("CC: ", cc)

#     if not sender_email or not sender_password:
#         return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     subject = f"An Update on Your Application for {vacancy.title} Role"
#     message = f"""
#     Dear {candidate_name},

#     Thank you for taking the time to apply for the {vacancy.title} position at {company} and for your interest in joining our team.

#     We appreciate the opportunity to learn about your skills and accomplishments. After careful review, we have decided to move forward with candidates whose experience more closely aligns with the specific requirements of this role.

#     This was a difficult decision due to the high volume of qualified applicants we received.

#     We encourage you to keep an eye on our careers page for future opportunities that may be a better fit for your background

#     We wish you the very best in your job search and future endeavors.

#     Sincerely,

#     Human Resouces Team, 
#     {company}
#     {hr.email}
#     """

#     print("Sending mail...")

#     # Create email with attachment
#     email = EmailMessage(subject=subject, body=message, from_email=sender_email, to=[vacancy_application.email], cc=cc, connection=connection)
#     email.send()
    
#     print("Mail Sent")


def send_vacancy_rejected_mail(request, application_id):
    vacancy_application = get_object_or_404(VacancyApplication, id=application_id, tenant=request.tenant)
    vacancy = vacancy_application.vacancy
    hr = request.user
    if not is_hr(hr):
        print(f"Unauthorized access by user {request.user.username}. Only HRs can perform this action")
        return render(request, 'tenant_error.html', {'error_code': '403','message': 'Only HRs can perform this action.'})
    
    sender_provider = hr.email_provider if hr.email_provider else SUPERUSER_EMAIL_PROVIDER
    sender_email = hr.email_address if hr.email_address else SUPERUSER_EMAIL_ADDRESS
    sender_password = hr.email_password if hr.email_password else SUPERUSER_EMAIL_PASSWORD
    candidate_name = vacancy_application.first_name.capitalize()
    company = vacancy_application.tenant.name

    if hr.email_provider and hr.email_address and hr.email_password:
        cc = []
    else:
        cc = [hr.email]
    
    print("CC: ", cc)

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    # Prepare context for the template
    context = {
        'candidate_name': candidate_name,
        'vacancy_title': vacancy.title,
        'company_name': company,
        'hr_email': hr.email,
        'hr_name': hr.get_full_name() or hr.username,
    }

    # Render HTML content
    html_content = render_to_string('emails/application_rejected.html', context)

    subject = f"An Update on Your Application for {vacancy.title} Role"

    print("Sending mail...")

    # Create and send HTML email
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender_email,
        to=[vacancy_application.email],
        cc=cc,
        connection=connection
    )
    
    # Specify that this is HTML email
    email.content_subtype = "html"
    
    email.send()
    
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
    paginator = Paginator(applications, 10)  # 10 applications per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'hr/accepted_applications.html', {'applications': page_obj, 'vacancy': vacancy})

@login_required
@user_passes_test(is_hr)
def fetch_rejected_applications(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    applications = VacancyApplication.objects.filter(vacancy=vacancy, status='rejected')
    paginator = Paginator(applications, 10)  # 10 applications per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'hr/rejected_applications.html', {'applications': page_obj, 'vacancy': vacancy})