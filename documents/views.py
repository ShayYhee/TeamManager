from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth import login, get_user_model
from django.contrib.auth.signals import user_logged_in
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.core.mail import send_mail, EmailMessage, get_connection
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Q
from django.dispatch import receiver
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils.text import slugify
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .forms import DocumentForm, SignUpForm, CreateDocumentForm, FileUploadForm, FolderForm, TaskForm, ReassignTaskForm, StaffProfileForm, StaffDocumentForm, EmailConfigForm, UserForm
from .models import Document, CustomUser, Role, File, Folder, Task, StaffProfile, Notification, UserNotification, StaffDocument, Event, EventParticipant, Department
from .serializers import EventSerializer
from .placeholders import replace_placeholders
from docx import Document as DocxDocument
from docx.shared import Inches
from ckeditor_uploader.views import upload as ckeditor_upload
import csv
import subprocess
import platform
import shutil
# from comtypes import CoInitialize, CoUninitialize
# from comtypes.client import CreateObject
# from win32com.client import Dispatch, constants, gencache
import pdfkit
from raadaa import settings
from html2docx import html2docx
from docx2txt import process
from datetime import datetime, date
import smtplib
from docx import Document as DocxDocument
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from bs4 import BeautifulSoup
from django.http import HttpResponse
import os
import requests
import io
import urllib.parse
from rest_framework import viewsets, permissions
import logging
logger = logging.getLogger(__name__)

pdf_config = pdfkit.configuration()

User = get_user_model()

def is_admin(user):
    # Check if the user is an admin

    for role in user.roles.all():
        if role.name == "Admin":
            return True

    # return user.is_staff

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

    print("Sending mail...")

    # Create email with attachment
    email = EmailMessage(subject, message, sender_email, list(bdm_emails), connection=connection)
    # email.attach_file(document.pdf_file.path)  # Attach the PDF
    email.send()

    # send_mail(
    #     subject,
    #     message,
    #     sender_email,  # Always send from Zoho SMTP email
    #     list(bdm_emails),  # Send to all BDMs
    #     connection=connection
    # )
    print("Mail Sent")

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

                    # try:
                    #     print("Starting PDF conversion")
                    #     CoInitialize()
                    #     word = CreateObject("Word.Application")
                    #     word.Visible = False
                    #     doc = word.Documents.Open(os.path.abspath(word_path))
                    #     doc.SaveAs(os.path.abspath(absolute_pdf_path), FileFormat=17)
                    #     doc.Close()
                    #     word.Quit()
                    #     CoUninitialize()
                    #     document.pdf_file = relative_pdf_path
                    #     document.save()
                    # except Exception as e:
                    #     print(f"PDF conversion error: {e}")
                    #     try:
                    #         CoUninitialize()
                    #     except:
                    #         pass
                    #     return HttpResponse(f"Error converting to PDF: {e}", status=500)
                    
                    # libreoffice_path = r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"

                    # Choose the right LibreOffice path
                    if platform.system() == "Windows":
                        paths = [
                            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                            r"C:\Program Files\LibreOffice\program\soffice.exe"
                        ]
                        libreoffice_path = next((p for p in paths if os.path.exists(p)), None)
                    else:
                        libreoffice_path = shutil.which("libreoffice")

                    # Check if LibreOffice exists
                    if not libreoffice_path or not os.path.exists(libreoffice_path):
                        raise FileNotFoundError("LibreOffice not found. Make sure it's installed and in PATH.")

                    try:
                        print("Starting PDF conversion with LibreOffice")
                        
                        # Ensure paths are absolute
                        abs_word_path = os.path.abspath(word_path)
                        abs_output_dir = os.path.dirname(os.path.abspath(absolute_pdf_path))

                        print("abs_word_path: ", abs_word_path)

                        # Run LibreOffice to convert .docx to .pdf
                        result = subprocess.run(
                            [libreoffice_path, "--headless", "--convert-to", "pdf", "--outdir", abs_output_dir, abs_word_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True
                        )

                        # Debug paths
                        print("LibreOffice path:", libreoffice_path)
                        print("abs_word_path:", abs_word_path)
                        print("abs_output_dir:", abs_output_dir)


                        print("LibreOffice stdout:", result.stdout.decode())
                        print("LibreOffice stderr:", result.stderr.decode())

                        # Confirm output PDF file path
                        if os.path.exists(absolute_pdf_path):
                            document.pdf_file = relative_pdf_path
                            document.save()
                        else:
                            return HttpResponse("PDF file was not generated.", status=500)

                    except subprocess.CalledProcessError as e:
                        print(f"LibreOffice conversion error: {e.stderr.decode()}")
                        return HttpResponse(f"Error converting to PDF: {e.stderr.decode()}", status=500)

                    except Exception as e:
                        print(f"Unexpected error: {e}")
                        return HttpResponse(f"Unexpected error converting to PDF: {e}", status=500)

                    print("Sending email")
                    send_approval_request(document)

                    print("Redirecting to document_list")
                    return redirect("document_list")

            #     print("Sending email")
            #     send_approval_request(document)
            
            # print("Redirecting to document_list")
            # return redirect("document_list")
        else:
            print("Formset errors:", formset.errors)
            print("Non-form errors:", formset.non_form_errors())
    else:
        print("GET request received")
        formset = DocumentFormSet()
    
    return render(request, "documents/create_document.html", {"formset": formset})

@user_passes_test(is_admin)
def users_list(request):
    users = CustomUser.objects.all().order_by('date_joined')
    paginator = Paginator(users, 10) # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "registration/users_list.html", {"users": page_obj})

@user_passes_test(is_admin)
def approve_user(request, user_id):
    user = CustomUser.objects.get(id=user_id)
    admin_user = CustomUser.objects.get(username=request.user)

    if user:
        user.is_active = True
        user.save()
        sender_email = admin_user.smtp_email
        sender_password = admin_user.smtp_password

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

        subject = f"Approval Request: {user.username}"
        message = f"""
        Dear {user.username},

        Your account has been activated, please click the link below to login: {'http://127.0.0.1:8000/login/'or 'https://raadaa.onrender.com/login'}

        Best regards,  
        {user.get_full_name()}
        """

        print("Sending mail...")

        send_mail(
        subject,
        message,
        sender_email,  # Always send from Zoho SMTP email
        [user.email],  # Send to all BDMs
        connection=connection
    )
        return redirect("users_list")

    return redirect("users_list")

def account_activation_sent(request):
    return render(request, "registration/account_activation_sent.html")

@user_passes_test(is_admin)
def edit_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == "POST":
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(User).pk,
                object_id=user.id,
                object_repr=user.username,
                action_flag=CHANGE,
                change_message='Edited user profile'
            )
            return redirect("users_list")
    else:
        form = UserForm(instance=user)
    return render(request, "registration/edit_user.html", {"form": form})

def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.is_active = "False"
            user.save()
            # approve_user(request, user.id)
            # login(request, user)
            # return redirect("login")  # Redirect to document form
            return redirect("account_activation_sent")
    else:
        form = SignUpForm()
    return render(request, "registration/register.html", {"form": form})

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)

    if user:
        user.delete()
        # return JsonResponse({'success': True})

    return redirect("users_list")  # Redirect back to the list

@login_required
def document_list(request):
    # Start with all documents
    documents = Document.objects.all()

    # Get filter parameters from the request
    company = request.GET.get('company', '').strip()
    doc_type = request.GET.get('type', '').strip()
    status = request.GET.get('status', '').strip()
    created = request.GET.get('created', '').strip()
    created_by = request.GET.get('created_by', '').strip()
    approved_by = request.GET.get('approved_by', '').strip()
    send_email = request.GET.get('send_email', '').strip()

    # Apply filters
    if company:
        documents = documents.filter(company_name__iexact=company)
        print(f"Filtering by company: {company}")
    if doc_type:
        documents = documents.filter(document_type__iexact=doc_type)
        print(f"Filtering by document_type: {doc_type}")
    if status:
        documents = documents.filter(status__iexact=status)
        print(f"Filtering by status: {status}")
    if created:
        try:
            documents = documents.filter(created_at__date=created)
            print(f"Filtering by created_at: {created}")
        except ValueError:
            print(f"Invalid date format for created: {created}")
    if created_by:
        documents = documents.filter(created_by__username__iexact=created_by)
        print(f"Filtering by created_by: {created_by}")
    if approved_by:
        documents = documents.filter(approved_by__username__iexact=approved_by)
        print(f"Filtering by approved_by: {approved_by}")
    if send_email:
        email_sent = send_email.lower() == 'sent'
        documents = documents.filter(email_sent=email_sent)
        print(f"Filtering by email_sent: {email_sent}")

    # Paginate filtered documents
    paginator = Paginator(documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get distinct values for filter dropdowns
    distinct_companies = Document.objects.values_list('company_name', flat=True).distinct()
    distinct_type = Document.objects.values_list('document_type', flat=True).distinct()
    distinct_created_by = User.objects.filter(
        id__in=Document.objects.values_list('created_by', flat=True).distinct()
    ).values_list('username', flat=True)
    distinct_approved_by = User.objects.filter(
        id__in=Document.objects.values_list('approved_by', flat=True).distinct()
    ).exclude(username__isnull=True).values_list('username', flat=True)

    # Debug filtered document count
    print(f"Filtered documents count: {documents.count()}")

    return render(request, "documents/document_list.html", {
        "documents": page_obj,
        "page_obj": page_obj,
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
    print("Yess>>>", request)
    print("Yess>>>", request.user)

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


# @user_passes_test(is_admin)
# def admin_access_page(request):
#     return render(request, "admin_access.html")

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

def add_formatted_content(doc, soup, word_dir):
    """Parse HTML and add formatted content and images to the .docx document."""
    current_paragraph = None

    def add_text_to_paragraph(text, bold=False, italic=False):
        """Helper to add text to the current paragraph with formatting."""
        nonlocal current_paragraph
        if not current_paragraph:
            current_paragraph = doc.add_paragraph()
        run = current_paragraph.add_run(text or '')
        run.bold = bold
        run.italic = italic

    for element in soup.find_all(recursive=False):  # Process top-level elements only
        if element.name == 'h1':
            current_paragraph = doc.add_heading(element.get_text(), level=1)
        elif element.name == 'h2':
            current_paragraph = doc.add_heading(element.get_text(), level=2)
        elif element.name == 'p':
            current_paragraph = doc.add_paragraph()
            # Process nested elements within <p>
            for child in element.children:
                if child.name == 'strong':
                    add_text_to_paragraph(child.get_text(), bold=True)
                elif child.name == 'em':
                    add_text_to_paragraph(child.get_text(), italic=True)
                elif child.name == 'img':
                    img_src = child.get('src')
                    if img_src:
                        try:
                            parsed_src = urllib.parse.urlparse(img_src)
                            if parsed_src.scheme in ('http', 'https'):
                                print(f"Downloading remote image: {img_src}")
                                response = requests.get(img_src, timeout=5)
                                if response.status_code == 200:
                                    img_data = io.BytesIO(response.content)
                                    doc.add_picture(img_data, width=Inches(4.0))
                                else:
                                    print(f"Failed to download image: {img_src} (Status: {response.status_code})")
                                    current_paragraph = doc.add_paragraph(f"[Image failed to load: {img_src}]")
                            else:
                                # Handle local images (e.g., /media/Uploads/image.jpg)
                                clean_src = img_src.replace(settings.MEDIA_URL, '').lstrip('/')
                                img_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, clean_src))
                                print(f"Attempting to add local image: {img_path}")
                                if os.path.exists(img_path):
                                    doc.add_picture(img_path, width=Inches(4.0))
                                else:
                                    print(f"Local image not found: {img_path}")
                                    current_paragraph = doc.add_paragraph(f"[Image not found: {img_path}]")
                        except Exception as e:
                            print(f"Error adding image {img_src}: {e}")
                            current_paragraph = doc.add_paragraph(f"[Error loading image: {img_src}]")
                else:
                    add_text_to_paragraph(child.get_text() if hasattr(child, 'get_text') else str(child))
        elif element.name == 'ul':
            current_paragraph = None
            for li in element.find_all('li', recursive=False):
                doc.add_paragraph(li.get_text(), style='ListBullet')
        elif element.name == 'ol':
            current_paragraph = None
            for li in element.find_all('li', recursive=False):
                doc.add_paragraph(li.get_text(), style='ListNumber')
        else:
            current_paragraph = None
            add_text_to_paragraph(element.get_text() if hasattr(element, 'get_text') else str(element))

@login_required
@csrf_exempt  # Required for CKEditor’s POST uploads
def custom_ckeditor_upload(request):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in to upload images.")
    logger.info(f"User {request.user.username} uploading image to CKEditor")
    response = ckeditor_upload(request)
    if response.status_code == 200:
        logger.info(f"Image upload successful for user {request.user.username}")
    else:
        logger.error(f"Image upload failed for user {request.user.username}: {response.content}")
    return response

def create_from_editor(request):
    if request.method == "POST":
        form = CreateDocumentForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data["title"]
            content = form.cleaned_data["content"]

            # Create a .docx file
            doc = DocxDocument()
            doc.add_heading(title, level=1)

            # Parse HTML content using BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')

            # Define file paths
            word_dir = os.path.join(settings.MEDIA_ROOT, "documents/word")
            pdf_dir = os.path.join(settings.MEDIA_ROOT, "documents/pdf")
            os.makedirs(word_dir, exist_ok=True)
            os.makedirs(pdf_dir, exist_ok=True)

            # Add formatted content and images
            add_formatted_content(doc, soup, word_dir)

            # Save the .docx file
            word_filename = f"{slugify(title)}.docx"
            word_path = os.path.join(word_dir, word_filename)
            try:
                doc.save(word_path)
                print(f"Saved .docx: {word_path}")
            except Exception as e:
                messages.error(request, f"Error creating .docx file: {e}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Generate and save the .pdf file using LibreOffice
            pdf_filename = f"{slugify(title)}.pdf"
            relative_pdf_path = os.path.join("documents/pdf", pdf_filename)
            absolute_pdf_path = os.path.join(settings.MEDIA_ROOT, relative_pdf_path)

            # Choose the right LibreOffice path
            if platform.system() == "Windows":
                paths = [
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                    r"C:\Program Files\LibreOffice\program\soffice.exe"
                ]
                libreoffice_path = next((p for p in paths if os.path.exists(p)), None)
            else:
                libreoffice_path = shutil.which("libreoffice") or shutil.which("soffice")

            # Check if LibreOffice exists
            if not libreoffice_path or not os.path.exists(libreoffice_path):
                messages.error(request, "LibreOffice not found. Make sure it's installed and in PATH.")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            try:
                print("Starting PDF conversion with LibreOffice")
                
                # Ensure paths are absolute
                abs_word_path = os.path.abspath(word_path)
                abs_output_dir = os.path.dirname(os.path.abspath(absolute_pdf_path))

                # Run LibreOffice to convert .docx to .pdf
                result = subprocess.run(
                    [libreoffice_path, "--headless", "--convert-to", "pdf", "--outdir", abs_output_dir, abs_word_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=30  # 30 seconds
                )

                # Debug paths
                print("LibreOffice path:", libreoffice_path)
                print("abs_word_path:", abs_word_path)
                print("abs_output_dir:", abs_output_dir)
                print("LibreOffice stdout:", result.stdout.decode())
                print("LibreOffice stderr:", result.stderr.decode())

                # Confirm output PDF file exists
                if not os.path.exists(absolute_pdf_path):
                    if os.path.exists(word_path):
                        os.remove(word_path)
                    messages.error(request, "PDF file was not generated.")
                    return render(request, 'documents/create_from_editor.html', {'form': form})

            except subprocess.CalledProcessError as e:
                print(f"LibreOffice conversion error: {e.stderr.decode()}")
                messages.error(request, f"Error converting to PDF: {e.stderr.decode()}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            except Exception as e:
                print(f"Unexpected error during PDF conversion: {e}")
                messages.error(request, f"Unexpected error converting to PDF: {e}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Save to database
            document = Document(
                document_type='Uploaded',
                document_source='editor',
                company_name='N/A',  # Adjust as needed
                company_address='N/A',
                contact_person_name='N/A',
                contact_person_email='N/A',
                contact_person_designation='N/A',
                sales_rep='N/A',
                created_by=request.user,
                word_file=f"documents/word/{word_filename}",
                pdf_file=relative_pdf_path
            )
            try:
                document.save()
            except Exception as e:
                messages.error(request, f"Error saving document: {e}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            messages.success(request, 'Document created successfully!')
            return redirect("document_list")
        else:
            print("Form errors:", form.errors)
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CreateDocumentForm()
    return render(request, 'documents/create_from_editor.html', {'form': form})


@login_required
def folder_list(request, parent_id=None):
    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, id=parent_id, created_by=request.user)

    folders = Folder.objects.filter(created_by=request.user, parent=parent)
    files = File.objects.filter(folder=parent, uploaded_by=request.user)

    folder_form = FolderForm(initial={'parent': parent})
    file_form = FileUploadForm()

    return render(request, 'documents/folder_list.html', {
        'parent': parent,
        'folders': folders,
        'files': files,
        'folder_form': folder_form,
        'file_form': file_form,
    })

@login_required
def create_folder(request):
    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.created_by = request.user
            parent_id = request.POST.get('parent')
            if parent_id:
                folder.parent = Folder.objects.get(id=parent_id)
            folder.save()
            return redirect('folder_list', folder.parent.id if folder.parent else '')
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))

@login_required
def delete_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, created_by=request.user)
    folder.delete()
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))

@login_required
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save(commit=False)
            uploaded_file.uploaded_by = request.user
            uploaded_file.original_name = request.FILES['file'].name
            uploaded_file.save()
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))

@login_required
def delete_file(request, file_id):
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user)
    file.delete()
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))

@login_required
def rename_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, created_by=request.user)
    if request.method == 'POST':
        new_name = request.POST.get('name')
        if new_name:
            folder.name = new_name
            folder.save()
    #         return JsonResponse({'success': True, 'new_name': folder.name})
    # return JsonResponse({'success': False}, status=400)
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))


@login_required
def rename_file(request, file_id):
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user)
    if request.method == 'POST':
        new_name = request.POST.get('name')
        if new_name:
            file.original_name = new_name
            file.save()
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))

@login_required
def move_folder(request, folder_id):
    folder = get_object_or_404(Folder, id=folder_id, created_by=request.user)
    if request.method == 'POST':
        new_parent_id = request.POST.get('new_parent_id')
        if new_parent_id:
            folder.parent = Folder.objects.get(id=new_parent_id)
            folder.save()
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))


@login_required
def move_file(request, file_id):
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user)
    if request.method == 'POST':
        new_folder_id = request.POST.get('new_folder_id')
        if new_folder_id:
            file.folder = Folder.objects.get(id=new_folder_id)
            file.save()
    return redirect(request.META.get('HTTP_REFERER', 'folder_list'))


@login_required
def create_task(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            form.save_m2m()  # Save documents relationship
            return redirect('task_list')  # You will define this page later
    else:
        form = TaskForm()
    return render(request, 'documents/create_task.html', {'form': form})

@login_required
def task_list(request):
    tasks = Task.objects.all()
    users = User.objects.all()
    status_labels = Task.STATUS_CHOICES
    overdue_tasks = Task.objects.filter(due_date__lt=date.today(), status__in=['pending', 'in_progress', 'on_hold'])
    overdue_tasks.update(status='overdue')
    context = {
        'tasks': tasks,
        'status_labels': status_labels,
        'today': date.today(),
        'user': request.user,
        'users': users,
    }
    # status_labels = [
    #     ('pending', 'Pending'),
    #     ('in_progress', 'In Progress'),
    #     ('on_hold', 'On Hold'),
    #     ('completed', 'Completed'),
    #     ('cancelled', 'Cancelled'),
    # ]
    return render(request, 'documents/task_list.html', context)

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    return render(request, 'documents/task_detail.html', {'task': task})



from django.http import JsonResponse
import json

@csrf_exempt
@login_required
def update_task_status(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id)
        data = json.loads(request.body)
        new_status = data.get('status')
        if new_status in dict(Task.STATUS_CHOICES):
            task.status = new_status
            task.save()
            return JsonResponse({'success': True, 'status': task.status})
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def reassign_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        form = ReassignTaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            return redirect('task_list')
    else:
        form = ReassignTaskForm(instance=task)
    return render(request, 'documents/reassign_task.html', {'form': form, 'task': task})

@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        task.delete()
        return redirect('task_list')
    return render(request, 'documents/confirm_delete.html', {'task': task})

@login_required
def task_edit(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            task = form.save()
            # Handle document uploads
            for file in request.FILES.getlist('documents'):
                Document.objects.create(task=task, pdf_file=file, company_name=file.name)
            return redirect('task_detail', task_id=task.id)
    else:
        form = TaskForm(instance=task)
    return render(request, 'documents/edit_task.html', {'form': form, 'task': task})

@login_required
def delete_task_document(request, task_id, doc_id):
    if request.method == 'POST':
        document = get_object_or_404(Document, id=doc_id, task__id=task_id)
        document.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

@login_required
def view_my_profile(request):
    profile, created = StaffProfile.objects.get_or_create(user=request.user)
    visible_fields = [
            "photo",
            "first_name", "last_name", "middle_name", "email", "phone_number", "sex", "date_of_birth", "home_address",
            "state_of_origin", "lga", "religion",
            "institution", "course", "degree", "graduation_year",
            "account_number", "bank_name", "account_name",
            "location", "employment_date",
            "organization", "department", "team", "designation", "official_email",
            "emergency_name", "emergency_relationship", "emergency_phone",
            "emergency_address", "emergency_email",
        ]
    return render(request, "documents/my_profile.html", {"profile": profile, "visible_fields": visible_fields})


@login_required
def edit_my_profile(request):
    profile,_ = StaffProfile.objects.get_or_create(user=request.user) # staff_profile = request.user.staff_profile  # Assuming one profile per user
    if request.method == 'POST':
        profile_form = StaffProfileForm(request.POST, request.FILES, instance=profile)
        
        if profile_form.is_valid():
            profile_form.save()
            return redirect('view_my_profile')  # Redirect to profile view or success page
    else:
        profile_form = StaffProfileForm(instance=profile)
        document_form = StaffDocumentForm()
        
    return render(request, 'documents/edit_profile.html', {
        'profile': profile,
        'profile_form': profile_form,
        'document_form': document_form,
    })

@login_required
def add_staff_document(request):
    if request.method == 'POST':
        form = StaffDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.staff_profile = get_object_or_404(StaffProfile, user=request.user)
            document.save()
            return JsonResponse({
                'success': True,
                'document': {
                    'id': document.id,
                    'description': document.description or document.document_type,
                    'file_url': document.file.url,
                    'document_type': document.get_document_type_display(),
                    'uploaded_at': document.uploaded_at.strftime('%B %d, %Y')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def delete_staff_document(request, document_id):
    try:
        # Get the user's StaffProfile (assuming one profile per user)
        staff_profile = StaffProfile.objects.get(user=request.user)
        document = get_object_or_404(StaffDocument, id=document_id, staff_profile=staff_profile)
        if request.method == 'POST':
            document.delete()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
    except StaffProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff profile not found'}, status=404)
    except StaffDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found or not owned by user'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@user_passes_test(is_admin)
def staff_directory(request):
    profiles = StaffProfile.objects.select_related("user", "organization").prefetch_related("team", "department").all()
    print(f"Profiles found: {profiles.count()}")  # Debug: Verify profiles
    
    grouped = {}
    for profile in profiles:
        org = profile.organization.name if profile.organization else "No Organization"
        depts = profile.department.all()
        if not depts:  # Handle profiles with no departments
            depts = [None]
        for dept in depts:
            dept_name = dept.name if dept else "No Department"
            teams = profile.team.all()
            if not teams:  # Handle profiles with no teams
                teams = [None]
            for team in teams:
                team_name = team.name if team else "No Team"
                grouped.setdefault(org, {}).setdefault(dept_name, {}).setdefault(team_name, []).append(profile)
    
    print(f"Grouped dictionary: {grouped}")  # Debug: Inspect grouped structure
    return render(request, "documents/staff_directory.html", {"grouped": grouped})


@login_required
def view_staff_profile(request, user_id):
    profile = get_object_or_404(StaffProfile, user_id=user_id)
    viewer = StaffProfile.objects.filter(user=request.user).first()
    visible_fields = [
        "photo",
        "first_name", "last_name", "middle_name", "email", "phone_number", "sex", "date_of_birth", "home_address",
        "state_of_origin", "lga", "religion",
        "institution", "course", "degree", "graduation_year",
        "account_number", "bank_name", "account_name",
        "location", "employment_date",
        "organization", "department", "team", "designation", "official_email",
        "emergency_name", "emergency_relationship", "emergency_phone",
        "emergency_address", "emergency_email",
    ]

    if viewer and profile.organization == viewer.organization:
        visible_fields += ["organization", "department"]
        if profile.department == viewer.department:
            shared_teams = set(profile.team.values_list("id", flat=True)) & set(viewer.team.values_list("id", flat=True))
            if shared_teams:
                visible_fields += ["team"]

    return render(request, "documents/view_staff_profile.html", {
        "profile": profile,
        "viewer": viewer,
        "visible_fields": visible_fields,
    })

def staff_list(request):
    # Get query parameters
    sort_by = request.GET.get('sort_by', 'name')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '')
    filter_dept = request.GET.get('dept', '')
    page = request.GET.get('page', 1)

    # Base queryset
    profiles = StaffProfile.objects.select_related('user', 'organization').prefetch_related('department', 'team')

    # Search by name
    if search_query:
        profiles = profiles.filter(
            Q(first_name__icontains=search_query) |
            Q(middle_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    # Filter by department
    if filter_dept:
        profiles = profiles.filter(department__name__iexact=filter_dept)

    # Sorting
    sort_field = sort_by
    if sort_by == 'name':
        sort_field = 'first_name'
    elif sort_by == 'department':
        sort_field = 'department__name'
    elif sort_by == 'team':
        sort_field = 'team__name'
    elif sort_by == 'photo':
        sort_field = 'photo'
    elif sort_by == 'organization':
        sort_field = 'organization__name'

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    profiles = profiles.order_by(sort_field)

    # Pagination
    paginator = Paginator(profiles, 10)  # 10 profiles per page
    page_obj = paginator.get_page(page)

    # Departments for filter dropdown
    departments = Department.objects.all()

    context = {
        'profiles': page_obj,
        'departments': departments,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'search_query': search_query,
        'filter_dept': filter_dept,
    }
    return render(request, 'documents/staff_list.html', context)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification, UserNotification
from django.utils.timezone import now

@login_required
def notifications_view(request):
    # Get all active notifications
    all_notifications = Notification.objects.filter(
        is_active=True
    ).order_by('-created_at')

    # Ensure UserNotification exists for each active notification
    active_notifications = []
    for notification in all_notifications:
        user_notification, created = UserNotification.objects.get_or_create(
            user=request.user,
            notification=notification,
            defaults={'seen_at': now(), 'dismissed': False}
        )
        if not user_notification.dismissed:
            active_notifications.append(user_notification)

    # Get dismissed notifications
    dismissed_notifications = UserNotification.objects.filter(
        user=request.user,
        dismissed=True
    ).select_related('notification').order_by('-seen_at')

    return render(request, 'documents/notifications.html', {
        'active_notifications': active_notifications,
        'dismissed_notifications': dismissed_notifications
    })

@require_POST
@login_required
def dismiss_notification(request):
    notification_id = request.POST.get('notification_id')
    try:
        notification = Notification.objects.get(id=notification_id)
        user_notification, created = UserNotification.objects.get_or_create(
            user=request.user,
            notification=notification,
            defaults={'seen_at': now()}
        )
        user_notification.dismissed = True
        user_notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

@require_POST
@login_required
def dismiss_all_notifications(request):
    try:
        # Update all non-dismissed UserNotifications for the user
        user_notifications = UserNotification.objects.filter(
            user=request.user,
            dismissed=False
        )
        updated_count = user_notifications.update(
            dismissed=True,
            seen_at=timezone.now()
        )
        return JsonResponse({'success': True, 'updated_count': updated_count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def email_config(request):
    user = CustomUser.objects.get(username=request.user.username)
    if request.method == 'POST':
        email_config_form = EmailConfigForm(request.POST, instance=user)
        if email_config_form.is_valid():
            email_config_form.save()
            return redirect('view_my_profile')
    else:
        email_config_form = EmailConfigForm(instance=user)
    return render(request, 'documents/email_config.html', {'email_config_form': email_config_form})

from django.db import models
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Event.objects.filter(
            models.Q(created_by=user) | models.Q(participants__user=user)
        ).distinct()

    def perform_create(self, serializer):
        print(f"Received data: {self.request.data}")
        event = serializer.save(created_by=self.request.user)

        # notif = Notification.objects.create(
        #     title=f"New Event: {event.title}",
        #     message=event.description or "You have been invited to a new event.",
        #     type=Notification.NotificationType.EVENT,
        #     expires_at=event.end_time,
        #     is_active=True
        # )

        # # Step 2: Create UserNotifications for each invited user
        # participants = self.request.data.get('participants', [])  # Should be list of user IDs
        # for user_id in participants:
        #     EventParticipant.objects.create(event=event, user=user_id, response="pending")
        #     UserNotification.objects.create(user=user_id, notification=notif)

    def update(self, request, *args, **kwargs):
        event = self.get_object()
        if event.created_by != request.user:
            return Response({"detail": "You can only edit events you created."}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        if event.created_by != request.user:
            return Response({"detail": "You can only delete events you created."}, status=403)
        return super().destroy(request, *args, **kwargs)

# @login_required
# def calendar_view(request):
#     token, created = Token.objects.get_or_create(user=request.user)
#     return render(request, 'documents/calendar.html', {'auth_token': token.key})
from django.middleware.csrf import get_token

@login_required
def calendar_view(request):
    # auth_token = None
    User = get_user_model()
    # if request.user.is_authenticated:
    #     auth_token = Token.objects.get(user=request.user).key if Token.objects.filter(user=request.user).exists() else None
    context = {
        # 'auth_token': auth_token or '',
        'csrf_token': get_token(request),
        'notification_bar_items': [],
        'birthday_others': [],
        'birthday_self': False,
        'users': User.objects.all(),
    }
    print(f"Context: {context}")  # Debug
    return render(request, 'documents/calendar.html', context)

def export_staff_csv(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    profile_ids = request.POST.getlist('profile_ids')
    if not profile_ids:
        return HttpResponse(status=400, content_type='application/json', content='{"error": "No profiles selected"}')

    profiles = StaffProfile.objects.filter(user__id__in=profile_ids).select_related('user', 'organization').prefetch_related('department', 'team')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="staff_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Phone Number', 'Email', 'Sex', 'Designation', 'Organization', 'Department', 'Team'])

    for profile in profiles:
        writer.writerow([
            f"{profile.first_name} {profile.middle_name or ''} {profile.last_name}".strip(),
            profile.phone_number or 'N/A',
            profile.email or 'N/A',
            profile.sex or 'N/A',
            profile.designation or 'N/A',
            profile.organization.name if profile.organization else 'N/A',
            ', '.join(profile.department.all().values_list('name', flat=True)) or 'N/A',
            ', '.join(profile.team.all().values_list('name', flat=True)) or 'N/A',
        ])

    return response