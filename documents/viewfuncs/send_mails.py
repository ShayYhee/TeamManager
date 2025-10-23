# For handling mails

from documents.models import CustomUser
from raadaa import settings
from .mail_connection import get_email_smtp_connection
from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string


main_superuser = CustomUser.objects.filter(is_superuser=True).first()

# Send Account registration Confirmation
# def send_reg_confirm(request, user, admin_user, sender_provider, sender_email, sender_password, sender):
#     sender_password = sender.get_smtp_password()
#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
#     base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
#     protocol = "http" if settings.DEBUG else "https"
#     login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/accounts/login"
#     subject = f"Account Approval: {user.username}"
#     message = f"""
#     Dear {user.username},

#     Your account has been successfully created. 
#     You can log in at: {login_url}

#     Best regards,  
#     {admin_user.get_full_name() or admin_user.username}
#     {admin_user.email}
#     """
#     try:
#         email = EmailMessage(subject, message, sender_email, [user.email], connection=connection, cc=[admin_user.email])
#         email.send()
#     except Exception as e:
#         print(f"Failed to send email: {e}")

def send_reg_confirm(request, user, admin_user, sender_provider, sender_email, sender_password, sender):
    sender_password = sender.get_smtp_password()
    # Configure SMTP settings dynamically
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)    
    base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
    protocol = "http" if settings.DEBUG else "https"
    login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/accounts/login"

    # Prepare context for the template
    context = {
        'user_name': user.username,
        'login_url': login_url,
        'tenant_name': request.tenant.name,
        'admin_name': admin_user.get_full_name() or admin_user.username,
        'admin_email': admin_user.email,
        'my_profile': f"{protocol}://{request.tenant.slug}.{base_domain}/dashboard/my-profile",
        'comp_profile': f"{protocol}://{request.tenant.slug}.{base_domain}/company-profile",
        'email_config': f"{protocol}://{request.tenant.slug}.{base_domain}/dashboard/email-config"
    }

    # Render HTML content
    html_content = render_to_string('emails/reg_confirm.html', context)

    subject = f"Account Approved: {user.username}"

    # Create and send HTML email
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender_email,
        to=[user.email],
        connection=connection
    )
    
    # Specify that this is HTML email
    email.content_subtype = "html"
    
    email.send()

# Template document approval
# def send_approval_request(document, sender_provider, sender_email, sender_password, bdm_emails):
#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     subject = f"Approval Request: {document.company_name}"
#     message = f"""
#     Dear BDM,

#     A new document for {document.company_name} has been created by {document.created_by.get_full_name()}.
#     Please review and approve it.

#     Best regards,  
#     {document.created_by.get_full_name()}
#     """

#     print("Sending mail...")

#     # Create email with attachment
#     email = EmailMessage(subject, message, sender_email, list(bdm_emails), connection=connection)
#     email.attach_file(document.pdf_file.path)  # Attach the PDF
#     email.send()
    
#     print("Mail Sent")

def send_approval_request(document, sender_provider, sender_email, sender_password, bdm_emails):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
    protocol = "http" if settings.DEBUG else "https"
    document_link = f"{protocol}://{document.tenant.slug}.{base_domain}/media/documents/pdf/{document.pdf_file.url}"
    # Prepare context for the template
    context = {
        'company_name': document.company_name,
        'creator_name': document.created_by.get_full_name(),
        'creator_title': getattr(document.created_by, 'title', ''),
        'created_date': document.created_at.strftime('%B %d, %Y'),
        'document_type': getattr(document, 'document_type', ''),
        'document_link': document_link,
    }

    # Render HTML content
    html_content = render_to_string('emails/approval_request.html', context)

    subject = f"Approval Request: {document.company_name}"

    print("Sending mail...")

    # Create email with HTML content and attachment
    email = EmailMessage(
        subject=subject,
        body=html_content,  # HTML content as the body
        from_email=sender_email,
        to=list(bdm_emails),
        connection=connection
    )
    
    # Specify that this is HTML email
    email.content_subtype = "html"
    
    # Attach the PDF file
    email.attach_file(document.pdf_file.path)
    
    email.send()
    
    print("Mail Sent")

# Send Template document approved email
# def send_doc_approved_bdm(request, document, sender_provider, sender_email, sender_password):
#     # Configure SMTP settings dynamically
#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     # Ensure the document's creator belongs to the same tenant
#     if document.created_by.tenant != request.tenant:
#         return HttpResponseForbidden("Invalid document creator for this company.")

#     # Send email notification to the BDA
#     subject = f"Document Approved for {request.tenant.name}"
#     message = (
#         f"Hello {document.created_by.username},\n\n"
#         f"Your document '{document.company_name} _ {document.document_type}' "
#         f"has been approved by {request.user.username} for tenant {request.tenant.name}."
#     )

#     email = EmailMessage(subject, message, sender_email, [document.created_by.email], connection=connection)
#     email.attach_file(document.pdf_file.path)  # Attach the PDF
#     email.send()

def send_doc_approved_bdm(request, document, sender_provider, sender_email, sender_password):
    # Configure SMTP settings dynamically
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
    protocol = "http" if settings.DEBUG else "https"
    document_link = f"{protocol}://{document.tenant.slug}.{base_domain}/media/documents/pdf/{document.pdf_file.url}"

    # Ensure the document's creator belongs to the same tenant
    if document.created_by.tenant != request.tenant:
        return HttpResponseForbidden("Invalid document creator for this company.")

    # Prepare context for the template
    context = {
        'creator_name': document.created_by.get_full_name() or document.created_by.username,
        'approver_name': request.user.get_full_name() or request.user.username,
        'company_name': document.company_name,
        'tenant_name': request.tenant.name,
        'document_type': getattr(document, 'document_type', ''),
        'document_link': document_link,
    }

    # Render HTML content
    html_content = render_to_string('emails/document_approved.html', context)

    subject = f"Document Approved for {request.tenant.name}"

    # Create and send HTML email
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender_email,
        to=[document.created_by.email],
        connection=connection
    )
    
    # Specify that this is HTML email
    email.content_subtype = "html"
    
    # Attach the PDF file
    email.attach_file(document.pdf_file.path)
    
    email.send()



# def send_approved_email_client(sender_provider, sender_email, sender_password, document, recipient, cc_list):
#     # Configure SMTP settings dynamically
#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     # Email subject based on document type
#     subject = (
#         f"{document.company_name} - Approved by AWS"
#         if document.document_type == "approval"
#         else f"{document.company_name} - SLA"
#     )

#     # Email body based on document type
#     if document.document_type == "approval":
#         message = f"""
#         Dear Sir,

#         Trust this email finds you well.

#         We are pleased to inform you that your projects have been officially approved by Amazon Web Services - AWS, under AWS Cloud Growth Services.

#         Congratulations on this accomplishment which shows your business has great potential to scale and thrive on AWS platform.  
#         This is a great achievement, and we are excited for you to proceed to the next phase.  
#         Please find the attached document for your reference which contains the relevant details for the next steps.

#         If you have any questions or need further clarification, please feel free to reach out to me.  
#         Once again, congratulations and we look forward to the continued success of your projects.

#         Thank you.

#         Best Regards,  
#         {document.created_by.get_full_name()} | Executive Assistant  
#         Transnet Cloud  
#         Mob: {document.created_by.phone_number}  
#         No 35 Ajose Adeogun Street Utako, Abuja  
#         Email: {document.created_by.email}  
#         Website: www.transnetcloud.com
#         """
#     else:  # SLA Document
#         message = f"""
#         Dear {document.company_name},

#         Trust this email finds you well.

#         Thank you for availing us your time and attention during our last meeting.  
#         We are delighted to move forward with your project on AWS to the next phase, be rest assured we will provide you with the necessary support your business needs to scale.

#         Please find attached the Service Level Agreement (SLA) document for your review. Kindly take a moment to go through the terms, and if they align with your expectations, we would appreciate you signing and returning the document at your earliest convenience.

#         Should you have any questions or require further clarification, please do not hesitate to reach out. Our team is readily available to assist you.

#         Thank you for choosing Transnet Cloud as your trusted partner.  

#         We look forward to a successful partnership.

#         Best Regards,  
#         {document.created_by.get_full_name()} | Executive Assistant  
#         Transnet Cloud  
#         Mob: {document.created_by.phone_number}  
#         No 35 Ajose Adeogun Street Utako, Abuja  
#         Email: {document.created_by.email}  
#         Website: www.transnetcloud.com
#         """

#     # Create email with attachment
#     email = EmailMessage(subject, message, sender_email, recipient, cc=cc_list, connection=connection)
#     email.attach_file(document.pdf_file.path)  # Attach the PDF
#     email.send()


def send_approved_email_client(sender_provider, sender_email, sender_password, document, recipient, cc_list):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    context = {
        'company_name': document.company_name,
        'creator_name': document.created_by.get_full_name(),
        'creator_title': 'Executive Assistant',
        'phone_number': getattr(document.created_by, 'phone_number', ''),
        'creator_email': document.created_by.email,
        'document_type': document.document_type,
    }

    if document.document_type == "approval":
        template_name = 'emails/aws_approval_client.html'
        subject = f"{document.company_name} - Approved by AWS"
    else:  # SLA Document
        template_name = 'emails/sla_document_client.html'
        subject = f"{document.company_name} - SLA"

    html_content = render_to_string(template_name, context)

    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender_email,
        to=recipient,
        cc=cc_list,
        connection=connection
    )
    
    email.content_subtype = "html"
    
    email.attach_file(document.pdf_file.path)
    
    email.send()

# def send_user_approved_email(request, user, admin_user, sender_provider, sender_email, sender_password):

#     # Set up email connection
#     connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

#     # Generate tenant-specific login URL
#     # Determine base domain based on environment
#     if settings.DEBUG:
#         base_domain = "127.0.0.1:8000"  # Local development
#         protocol = "http"
#     else:
#         base_domain = "teammanager.ng"  # Production
#         protocol = "https"

#     # Generate tenant-specific login URL
#     login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/accounts/login"

#     # Prepare email
#     subject = f"Account Approval: {user.username}"
#     message = f"""
#     Dear {user.username},

#     Your account has been activated. Please click the link below to log in:
#     {login_url}

#     Best regards,  
#     {admin_user.get_full_name() or admin_user.username}
#     """

#     print("Sending mail...")

#     try:
#         # Send email to the user
#         send_mail(
#             subject,
#             message,
#             sender_email,
#             [user.email],
#             connection=connection,
#         )
#     except Exception as e:
#         print(f"Failed to send email: {e}")
#         return HttpResponseForbidden("Failed to send approval email. Contact admin.")


def send_user_approved_email(request, user, admin_user, sender_provider, sender_email, sender_password):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
    if error_message:
        print(f"SMTP Error: {error_message}")
        return HttpResponseForbidden("Email service unavailable.")

    # Generate tenant-specific login URL
    protocol = "http" if settings.DEBUG else "https"
    base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
    login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/accounts/login"

    context = {
        'username': user.username,
        'full_name': user.get_full_name() or user.username,
        'admin_name': admin_user.get_full_name() or admin_user.username,
        'tenant_name': request.tenant.name,
        'login_url': login_url,
        'user': user,  # for footer email link
    }

    html_content = render_to_string('emails/user_approved.html', context)
    subject = f"Account Approved - Welcome to {request.tenant.name}!"

    print("Sending approval email...")

    try:
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=sender_email,
            to=[user.email],
            connection=connection
        )
        email.content_subtype = "html"
        email.send()
        print("Approval email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")
        return HttpResponseForbidden("Failed to send approval email. Contact admin.")
    

# def send_vac_app_received_email(sender_provider, sender_email, sender_password, company, candidate_name, vacancy_application, vacancy):
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
    

# def send_vac_app_received_email(sender_provider, sender_email, sender_password, company, candidate_name, vacancy_application, vacancy):
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

def send_vac_app_received_email(sender_provider, sender_email, sender_password, company, candidate_name, vacancy_application, vacancy):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
    if error_message:
        print(f"SMTP Connection Failed: {error_message}")
        return  # Or raise/log as needed

    context = {
        'candidate_name': candidate_name,
        'vacancy_title': vacancy.title,
        'company_name': company,
        'application_date': vacancy_application.created_at.strftime('%B %d, %Y'),
        'vacancy_application': vacancy_application,  # For ID in footer
    }

    html_content = render_to_string('emails/application_received.html', context)
    subject = f"Application Received for {vacancy.title} Role"

    print(f"Sending application confirmation to {vacancy_application.email}...")

    try:
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=sender_email,
            to=[vacancy_application.email],
            connection=connection
        )
        email.content_subtype = "html"
        email.send()
        print("Application received email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Optionally log or notify admin

# def send_vac_app_accepted_email(sender_provider, sender_email, sender_password, company, candidate_name, hr, cc, vacancy_application, vacancy):
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

def send_vac_app_accepted_email(sender_provider, sender_email, sender_password, company, candidate_name, hr, cc, vacancy_application, vacancy):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
    if error_message:
        print(f"SMTP Error: {error_message}")
        return  # Handle gracefully

    context = {
        'candidate_name': candidate_name,
        'vacancy_title': vacancy.title,
        'company_name': company,
        'hr_email': hr.email,
        'hr_name': hr.get_full_name() or hr.username,
        'vacancy_application': vacancy_application,  # For ID
    }

    html_content = render_to_string('emails/application_accepted.html', context)
    subject = f"You're Moving Forward! Next Steps for the {vacancy.title} Role"

    print(f"Sending acceptance email to {vacancy_application.email}...")

    try:
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=sender_email,
            to=[vacancy_application.email],
            cc=cc or [],
            connection=connection
        )
        email.content_subtype = "html"
        email.send()
        print("Acceptance email sent successfully.")
    except Exception as e:
        print(f"Email failed: {e}")
        # Log or notify admin

# def send_vac_app_rejected_email(sender_provider, sender_email, sender_password, company, candidate_name, hr, cc, vacancy_application, vacancy):
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

def send_vac_app_rejected_email(sender_provider, sender_email, sender_password, company, candidate_name, hr, cc, vacancy_application, vacancy):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
    if error_message:
        print(f"SMTP Error: {error_message}")
        return

    context = {
        'candidate_name': candidate_name,
        'vacancy_title': vacancy.title,
        'company_name': company,
        'hr_email': hr.email,
        'hr_name': hr.get_full_name() or hr.username,
        'vacancy_application': vacancy_application,  # For ID
    }

    html_content = render_to_string('emails/application_rejected.html', context)
    subject = f"An Update on Your Application for {vacancy.title} Role"

    print(f"Sending rejection email to {vacancy_application.email}...")

    try:
        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=sender_email,
            to=[vacancy_application.email],
            cc=cc or [],
            connection=connection
        )
        email.content_subtype = "html"
        email.send()
        print("Rejection email sent.")
    except Exception as e:
        print(f"Email failed: {e}")