from django.shortcuts import render, redirect
from .forms import DocumentForm, SignUpForm
from .models import Document, CustomUser
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.signals import user_logged_in
from docx import Document as DocxDocument
from comtypes import CoInitialize, CoUninitialize
from comtypes.client import CreateObject
import pdfkit
from django.conf import settings
from doc_system import settings
import os
from django.http import HttpResponse, HttpResponseForbidden
from docx2txt import process
from datetime import datetime
from .placeholders import replace_placeholders
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, EmailMessage, get_connection
from django.dispatch import receiver
import smtplib

pdf_config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")  # Set full path

User = get_user_model()

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.conf import settings

def send_approval_request(document):
    # Get all BDM emails
    bdm_emails = User.objects.filter(role="BDM").values_list("email", flat=True)

    # Ensure there are BDMs to notify
    if not bdm_emails:
        return
    
    sender_email = document.created_by.smtp_email
    sender_password = document.created_by.smtp_password

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="smtp.zoho.com",
        port=587,
        username=sender_email,
        password=sender_password,
        use_tls=True,
    )

    subject = f"Approval Request: {document.company_name}"
    message = f"""
    Dear BDM,

    A new document for {document.company_name} has been created by {document.created_by.get_full_name()}.
    Please review and approve it.

    Best regards,  
    {document.created_by.get_full_name()}
    """

    send_mail(
        subject,
        message,
        sender_email,  # Always send from Zoho SMTP email
        list(bdm_emails),  # Send to all BDMs
        connection=connection
    )

    # email = EmailMessage(subject, message, sender_email, list(bdm_emails))
    # email.send()

@login_required
def create_document(request):
    if request.method == "POST":
        form = DocumentForm(request.POST)
        if form.is_valid():
            document = form.save(commit=False)
            document.created_by = request.user
            document.save()

            # Template setup
            template_filename = "Approval Letter Template.docx" if document.document_type == "approval" else "SLA Template.docx"
            template_path = os.path.join(settings.BASE_DIR, "documents/templates/docx_templates", template_filename)
            if not os.path.exists(template_path):
                return HttpResponse(f"Error: Template not found at {template_path}", status=500)
            
            # Get the current date
            today = datetime.today()

            # Format date based on document type
            if document.document_type == "approval":
                day = today.day
                suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
                formatted_date = today.strftime("%d") + suffix + " " + today.strftime("%d %B, %Y")  # Example: 25th March, 2025
            else:
                formatted_date = today.strftime("%m/%d/%Y")  # Example: 03/25/2025

            # Edit Word doc
            doc = DocxDocument(template_path)
            replacements = {
                "{{Company Name}}": document.company_name,
                "{{Company Address}}": document.company_address,
                "{{Contact Person Name}}": document.contact_person_name,
                "{{Contact Person Email}}": document.contact_person_email,
                "{{Contact Person Designation}}": document.contact_person_designation + ",",
                "{{Sales Rep}}": document.sales_rep,
                "{{Date}}": formatted_date,
            }
            doc = replace_placeholders(doc, replacements, document.document_type)


            # Save Word doc
            word_dir = os.path.join(settings.MEDIA_ROOT, "documents/word")
            os.makedirs(word_dir, exist_ok=True)
            word_filename = f"{document.company_name}_approval.docx" if document.document_type == "approval" else f"{document.company_name}_sla.docx"
            word_path = os.path.join(word_dir, word_filename)
            doc.save(word_path)
            document.word_file = word_path
            document.save()

            ## Send approval request email
            send_approval_request(document)

            # Convert to PDF using Word COM
            pdf_dir = os.path.join(settings.MEDIA_ROOT, "documents/pdf")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, word_filename.replace(".docx", ".pdf"))

            try:
                # Initialize COM
                CoInitialize()  # Add this line
                word = CreateObject("Word.Application")
                word.Visible = False  # Run in background
                doc = word.Documents.Open(os.path.abspath(word_path))
                # 17 is the wdFormatPDF constant
                doc.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
                doc.Close()
                word.Quit()
                # Cleanup COM
                CoUninitialize()  # Add this line
                document.pdf_file = pdf_path
                document.save()
            except Exception as e:
                # Ensure COM is uninitialized even if an error occurs
                try:
                    CoUninitialize()
                except:
                    pass
                return HttpResponse(f"Error converting to PDF: {e}", status=500)

            return redirect("document_list")
    else:
        form = DocumentForm()
    return render(request, "documents/create_document.html", {"form": form})


def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            login(request, user)
            return redirect("login")  # Redirect to document form
    else:
        form = SignUpForm()
    return render(request, "documents/register.html", {"form": form})

@login_required
def document_list(request):
    documents = Document.objects.all()
    return render(request, "documents/document_list.html", {"documents": documents})

def home(request):
    return render(request, "documents/home.html")


@login_required
def approve_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Restrict only BDMs from approving
    if request.user.role != "BDM":
        return HttpResponseForbidden("You are not allowed to approve this document.")

    document.status = "approved"
    document.approved_by = request.user
    document.save()

    # Ensure the BDM has SMTP credentials
    sender_email = request.user.smtp_email
    sender_password = request.user.smtp_password

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    # Configure SMTP settings dynamically
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="smtp.zoho.com",
        port=587,
        username=sender_email,
        password=sender_password,
        use_tls=True,
    )

    # Send email notification to the BDA
    subject = "Your Document Has Been Approved"
    message = f"Hello {document.created_by.username},\n\nYour document '{document.company_name} _ {document.document_type}' has been approved by {request.user.username}."

    send_mail(
        subject,
        message,
        sender_email,  # Logged-in BDM's email
        [document.created_by.email],  # BDA's email
        connection=connection,  # Use dynamic SMTP connection
    )

    return redirect("document_list")  # Redirect to dashboard

# def get_sr_email(document, sales_rep):
#     return CustomUser.objects.filter(fullname={document.sales_rep}).values_list("email", flat=True)


def send_approved_email(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Ensure the document is approved before sending an email
    if document.status != "approved":
        return HttpResponseForbidden("This document is not approved yet.")

    # Check if the email was already sent
    if document.email_sent:
        return HttpResponseForbidden("Email has already been sent.")

    # Ensure the PDF file exists
    if not document.pdf_file or not os.path.exists(document.pdf_file.path):
        return HttpResponseForbidden("PDF file not found.")

    # Get sender credentials from the logged-in user
    sender_email = request.user.smtp_email
    sender_password = request.user.smtp_password

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")
    
    # Define recipient, CC, and attachment
    # recipient = [document.contact_person_email]  # Main recipient

    # sales_rep_email = User.objects.filter(first_name={document.sales_rep.split(" ")[0]}, last_name={document.sales_rep.split(" ")[1]}).values_list("email", flat=True)
    # bdm_emails = User.objects.filter(role="BDM").values_list("email", flat=True)
    # print(bdm_emails)
    # cc_list = [sales_rep_email, bdm_emails]

    # cc_list = [document.sales_rep, document.bdm_email]  # CC Sales Rep & BDM

    # Configure SMTP settings dynamically
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="smtp.zoho.com",
        port=587,
        username=sender_email,
        password=sender_password,
        use_tls=True,
    )

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
    email = EmailMessage(subject, message, sender_email, [document.contact_person_email],connection=connection)
    email.attach_file(document.pdf_file.path)  # Attach the PDF
    email.send()

    # Update email status
    document.email_sent = True
    document.save()

    return redirect("document_list")  # Redirect to the document list
def is_admin(user):
    return user.is_staff

@login_required
@user_passes_test(is_admin)
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Ensure document files are deleted from storage
    if document.word_file:
        document.word_file.delete(save=False)
    if document.pdf_file:
        document.pdf_file.delete(save=False)

    document.delete()
    return redirect("document_list")  # Redirect back to the list