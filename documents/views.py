from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import login, get_user_model
from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail, EmailMessage, get_connection
from django.dispatch import receiver
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.conf import settings
from django.forms import formset_factory
from django.db.models import Q
from .forms import DocumentForm, SignUpForm
from .models import Document, CustomUser, Role
from .placeholders import replace_placeholders
from docx import Document as DocxDocument
from comtypes import CoInitialize, CoUninitialize
from comtypes.client import CreateObject
# from win32com.client import Dispatch, constants, gencache
import pdfkit
from doc_system import settings
import os
from docx2txt import process
from datetime import datetime
import smtplib


pdf_config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")  # Set full path

User = get_user_model()

def send_approval_request(document):
    # Get all BDM emails
    bdm_emails = User.objects.filter(position="BDM").values_list("email", flat=True)

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
    DocumentFormSet = formset_factory(DocumentForm, extra=1)
    
    if request.method == "POST":
        print("POST request received")
        formset = DocumentFormSet(request.POST, request.FILES)
        print("Formset data:", request.POST)
        print("Files:", request.FILES)

        if formset.is_valid():
            print("Formset is valid")
            for form in formset:
                if form.has_changed():
                    print("Processing form:", form.cleaned_data)
                    document = form.save(commit=False)
                    document.created_by = request.user
                    document.save()

                    creation_method = form.cleaned_data['creation_method']
                    word_dir = os.path.join(settings.MEDIA_ROOT, "documents/word")
                    pdf_dir = os.path.join(settings.MEDIA_ROOT, "documents/pdf")
                    os.makedirs(word_dir, exist_ok=True)
                    os.makedirs(pdf_dir, exist_ok=True)

                    base_filename = f"{document.company_name}_{document.id}"

                    if creation_method == 'template':
                        template_filename = "Approval Letter Template.docx" if document.document_type == "approval" else "SLA Template.docx"
                        template_path = os.path.join(settings.BASE_DIR, "documents/templates/docx_templates", template_filename)
                        if not os.path.exists(template_path):
                            print(f"Template not found: {template_path}")
                            return HttpResponse(f"Error: Template not found at {template_path}", status=500)
                        
                        today = datetime.today()
                        if document.document_type == "approval":
                            day = today.day
                            suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
                            formatted_date = today.strftime("%d") + suffix + " " + today.strftime("%d %B, %Y")
                        else:
                            formatted_date = today.strftime("%m/%d/%Y")

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

                        word_filename = f"{base_filename}.docx"
                        word_path = os.path.join(word_dir, word_filename)
                        doc.save(word_path)
                        document.word_file = os.path.join("documents/word", word_filename)
                    else:
                        uploaded_file = form.cleaned_data['uploaded_file']
                        file_extension = uploaded_file.name.lower().split('.')[-1]

                        if file_extension == 'docx':
                            word_filename = f"{base_filename}.docx"
                            word_path = os.path.join(word_dir, word_filename)
                            with open(word_path, 'wb') as f:
                                for chunk in uploaded_file.chunks():
                                    f.write(chunk)
                            document.word_file = os.path.join("documents/word", word_filename)
                        elif file_extension == 'pdf':
                            pdf_filename = f"{base_filename}.pdf"
                            pdf_path = os.path.join(pdf_dir, pdf_filename)
                            with open(pdf_path, 'wb') as f:
                                for chunk in uploaded_file.chunks():
                                    f.write(chunk)
                            document.pdf_file = os.path.join("documents/pdf", pdf_filename)
                            document.save()
                            print("Sending email for uploaded PDF")
                            send_approval_request(document)
                            continue

                    pdf_filename = f"{base_filename}.pdf"
                    relative_pdf_path = os.path.join("documents/pdf", pdf_filename)
                    absolute_pdf_path = os.path.join(settings.MEDIA_ROOT, relative_pdf_path)

                    try:
                        print("Starting PDF conversion")
                        CoInitialize()
                        word = CreateObject("Word.Application")
                        word.Visible = False
                        doc = word.Documents.Open(os.path.abspath(word_path))
                        doc.SaveAs(os.path.abspath(absolute_pdf_path), FileFormat=17)
                        doc.Close()
                        word.Quit()
                        CoUninitialize()
                        document.pdf_file = relative_pdf_path
                        document.save()
                    except Exception as e:
                        print(f"PDF conversion error: {e}")
                        try:
                            CoUninitialize()
                        except:
                            pass
                        return HttpResponse(f"Error converting to PDF: {e}", status=500)

                    print("Sending email")
                    send_approval_request(document)
            
            print("Redirecting to document_list")
            return redirect("document_list")
        else:
            print("Formset errors:", formset.errors)
            print("Non-form errors:", formset.non_form_errors())
    else:
        print("GET request received")
        formset = DocumentFormSet()
    
    return render(request, "documents/create_document.html", {"formset": formset})

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
    # Start with all documents
    documents = Document.objects.all()

    # Get filter parameters from the request
    company = request.GET.get('company', '')
    doc_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    created = request.GET.get('created', '')
    created_by = request.GET.get('created_by', '')
    approved_by = request.GET.get('approved_by', '')
    send_email = request.GET.get('send_email', '')

    # Apply filters if parameters are provided
    if company:
        documents = documents.filter(company_name__iexact=company)
    if doc_type:
        documents = documents.filter(document_type__icontains=doc_type)
    if status:
        documents = documents.filter(status__iexact=status)
    if created:
        documents = documents.filter(created_at__date=created)
    if created_by:
        documents = documents.filter(created_by__username__icontains=created_by)
    if approved_by:
        documents = documents.filter(approved_by__username__icontains=approved_by)
    if send_email:
        documents = documents.filter(email_sent=(send_email.lower() == 'sent'))

    distinct_companies = Document.objects.values_list('company_name', flat=True).distinct()
    distinct_type = Document.objects.values_list('document_type', flat=True).distinct()
    distinct_created_by = User.objects.filter(id__in=Document.objects.values_list('created_by', flat=True).distinct())
    distinct_approved_by = User.objects.filter(id__in=Document.objects.values_list('approved_by', flat=True).distinct())

    return render(request, "documents/document_list.html", {
        "documents": documents,
        "filter_params": {
            'company': company,
            'type': doc_type,
            'status': status,
            'created': created,
            'created_by': created_by,
            'approved_by': approved_by,
            'send_email': send_email,
        },
        "distinct_companies": distinct_companies,
        "distinct_type": distinct_type,
        "distinct_created_by": distinct_created_by,
        "distinct_approved_by": distinct_approved_by
    })

def home(request):
    return render(request, "documents/home.html")


@login_required
def approve_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Restrict only BDMs from approving
    if request.user.position != "BDM":
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

def autocomplete_sales_rep(request):
    if 'term' in request.GET:
        qs = User.objects.filter(
            roles__name='Sales Rep',
            username__icontains=request.GET.get('term')
        ).distinct()
        names = list(qs.values_list('username', flat=True))
        return JsonResponse(names, safe=False)


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

    # Main recipient
    raw_recipients = document.contact_person_email  # e.g., "email1@example.com, email2@example.com"
    recipient = [email.strip() for email in raw_recipients.split(",") if email.strip()] # in case of multiple emails

    # recipient = [document.contact_person_email]

    # Get Sales Rep email
    sales_rep_email = User.objects.filter(username=document.sales_rep).values_list("email", flat=True)

    # Get all BDM emails
    bdm_emails = User.objects.filter(position="BDM").values_list("email", flat=True)

    # Combine into a single list
    cc_list = list(sales_rep_email) + list(bdm_emails)


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
    email = EmailMessage(subject, message, sender_email, recipient, cc=cc_list, connection=connection)
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