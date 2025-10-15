# For handling mails

from documents.models import CustomUser
from raadaa import settings
from .mail_connection import get_email_smtp_connection
from django.shortcuts import render
from django.http.response import HttpResponseForbidden
from django.core.mail import send_mail, EmailMessage

# Send Account registration Confirmation
def send_reg_confirm(request, user, admin_user, sender_provider, sender_email, sender_password):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
    base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
    protocol = "http" if settings.DEBUG else "https"
    login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/accounts/login"
    subject = f"Account Pending Approval: {user.username}"
    message = f"""
    Dear {user.username},

    Your account has been created and is pending approval. You will be notified once approved. 
    Once activated, you can log in at: {login_url}

    Best regards,  
    {admin_user.get_full_name() or admin_user.username}
    """
    try:
        send_mail(subject, message, sender_email, [user.email], connection=connection)
    except Exception as e:
        print(f"Failed to send email: {e}")

# Template document approval
def send_approval_request(document, sender_provider, sender_email, sender_password, bdm_emails):
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    subject = f"Approval Request: {document.company_name}"
    message = f"""
    Dear BDM,

    A new document for {document.company_name} has been created by {document.created_by.get_full_name()}.
    Please review and approve it.

    Best regards,  
    {document.created_by.get_full_name()}
    """

    print("Sending mail...")

    # Create email with attachment
    email = EmailMessage(subject, message, sender_email, list(bdm_emails), connection=connection)
    email.attach_file(document.pdf_file.path)  # Attach the PDF
    email.send()
    
    print("Mail Sent")

# Send Template document approved email
def send_doc_approved_bdm(request, document, sender_provider, sender_email, sender_password):
    # Configure SMTP settings dynamically
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    # Ensure the document's creator belongs to the same tenant
    if document.created_by.tenant != request.tenant:
        return HttpResponseForbidden("Invalid document creator for this company.")

    # Send email notification to the BDA
    subject = f"Document Approved for {request.tenant.name}"
    message = (
        f"Hello {document.created_by.username},\n\n"
        f"Your document '{document.company_name} _ {document.document_type}' "
        f"has been approved by {request.user.username} for tenant {request.tenant.name}."
    )

    email = EmailMessage(subject, message, sender_email, [document.created_by.email], connection=connection)
    email.attach_file(document.pdf_file.path)  # Attach the PDF
    email.send()


def send_approved_email_client(sender_provider, sender_email, sender_password, document, recipient, cc_list):
    # Configure SMTP settings dynamically
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    # Email subject based on document type
    subject = (
        f"{document.company_name} - Approved by AWS"
        if document.document_type == "approval"
        else f"{document.company_name} - SLA"
    )

    # Email body based on document type
    if document.document_type == "approval":
        message = f"""
        Dear Sir,

        Trust this email finds you well.

        We are pleased to inform you that your projects have been officially approved by Amazon Web Services - AWS, under AWS Cloud Growth Services.

        Congratulations on this accomplishment which shows your business has great potential to scale and thrive on AWS platform.  
        This is a great achievement, and we are excited for you to proceed to the next phase.  
        Please find the attached document for your reference which contains the relevant details for the next steps.

        If you have any questions or need further clarification, please feel free to reach out to me.  
        Once again, congratulations and we look forward to the continued success of your projects.

        Thank you.

        Best Regards,  
        {document.created_by.get_full_name()} | Executive Assistant  
        Transnet Cloud  
        Mob: {document.created_by.phone_number}  
        No 35 Ajose Adeogun Street Utako, Abuja  
        Email: {document.created_by.email}  
        Website: www.transnetcloud.com
        """
    else:  # SLA Document
        message = f"""
        Dear {document.company_name},

        Trust this email finds you well.

        Thank you for availing us your time and attention during our last meeting.  
        We are delighted to move forward with your project on AWS to the next phase, be rest assured we will provide you with the necessary support your business needs to scale.

        Please find attached the Service Level Agreement (SLA) document for your review. Kindly take a moment to go through the terms, and if they align with your expectations, we would appreciate you signing and returning the document at your earliest convenience.

        Should you have any questions or require further clarification, please do not hesitate to reach out. Our team is readily available to assist you.

        Thank you for choosing Transnet Cloud as your trusted partner.  

        We look forward to a successful partnership.

        Best Regards,  
        {document.created_by.get_full_name()} | Executive Assistant  
        Transnet Cloud  
        Mob: {document.created_by.phone_number}  
        No 35 Ajose Adeogun Street Utako, Abuja  
        Email: {document.created_by.email}  
        Website: www.transnetcloud.com
        """

    # Create email with attachment
    email = EmailMessage(subject, message, sender_email, recipient, cc=cc_list, connection=connection)
    email.attach_file(document.pdf_file.path)  # Attach the PDF
    email.send()