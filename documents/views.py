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
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
from django.db.models import Q, F
from django.dispatch import receiver
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils.text import slugify
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .forms import DocumentForm, SignUpForm, CreateDocumentForm, FileUploadForm, FolderForm, TaskForm, ReassignTaskForm, StaffProfileForm, StaffDocumentForm, EmailConfigForm, UserForm, PublicFolderForm, PublicFileForm
from .models import Document, CustomUser, Role, File, Folder, Task, StaffProfile, Notification, UserNotification, StaffDocument, Event, EventParticipant, Department, Team, PublicFile, PublicFolder
from raadaa.settings import ALLOWED_HOSTS
from .serializers import EventSerializer
from .placeholders import replace_placeholders
from docx import Document as DocxDocument
from docx.shared import Inches
from ckeditor_uploader.views import upload as ckeditor_upload
import csv
import subprocess
import platform
import shutil
import pdfkit
import re
from raadaa import settings
from html2docx import html2docx
from docx2txt import process
from datetime import datetime, date, timedelta
import smtplib
from docx.enum.text import WD_ALIGN_PARAGRAPH
from bs4 import BeautifulSoup
from django.http import HttpResponse
import os
import requests
import io
import urllib.parse
from rest_framework import viewsets, permissions
import json
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
    # Get all BDM emails for the document's tenant
    bdm_emails = CustomUser.objects.filter(
        tenant=document.tenant,  # Filter by the document's tenant
        roles__name="BDM"
    ).values_list("email", flat=True)

    # Ensure there are BDMs to notify
    if not bdm_emails:
        return
    
    # Ensure the document's creator is from the same tenant
    if document.created_by.tenant != document.tenant:
        return HttpResponseForbidden("Unauthorized: Creator does not belong to the document's tenant.")

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
    email.attach_file(document.pdf_file.path)  # Attach the PDF
    email.send()
    
    print("Mail Sent")


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
                    document.tenant = request.tenant  # Set tenant from middleware
                    # Validate that the user belongs to the same tenant
                    if document.created_by.tenant != request.tenant:
                        return HttpResponse("Unauthorized: User does not belong to the current tenant.", status=403)

                    # Get or create the "Template Document" folder
                    user = request.user
                    department = user.department if hasattr(user, 'department') else None
                    team = user.teams.first() if hasattr(user, 'teams') and user.teams.exists() else None

                    # Ensure user has a department or team
                    if not department and not team:
                        return HttpResponse("Error: User must be associated with a department or team.", status=403)

                    # Choose department or team for the folder (prefer department if available)
                    folder_defaults = {
                        'created_by': user,
                        'department': department,
                        'team': team if not department else None  # Use team only if no department
                    }

                    try:
                        template_folder, created = PublicFolder.objects.get_or_create(
                            tenant=request.tenant,
                            name="Template Document",
                            defaults=folder_defaults
                        )
                    except ValidationError as e:
                        print(f"PublicFolder creation error: {e}")
                        return HttpResponse(f"Error creating Template Document folder: {e}", status=400)

                    # Validate folder access (similar to create_public_folder)
                    if template_folder.department and template_folder.department != user.department:
                        return HttpResponse("Invalid Department for Template Document folder.", status=403)
                    if template_folder.team and template_folder.team not in user.teams.all():
                        return HttpResponse("Invalid Team for Template Document folder.", status=403)

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

                        # Save Word file to PublicFile
                        public_word_file = PublicFile(
                            tenant=request.tenant,
                            original_name=word_filename,
                            file=os.path.join("documents/word", word_filename),
                            folder=template_folder,
                            created_by=user
                        )
                        public_word_file.save()
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

                            # Save Word file to PublicFile
                            public_word_file = PublicFile(
                                tenant=request.tenant,
                                original_name=word_filename,
                                file=os.path.join("documents/word", word_filename),
                                folder=template_folder,
                                created_by=user
                            )
                            public_word_file.save()
                        elif file_extension == 'pdf':
                            pdf_filename = f"{base_filename}.pdf"
                            pdf_path = os.path.join(pdf_dir, pdf_filename)
                            with open(pdf_path, 'wb') as f:
                                for chunk in uploaded_file.chunks():
                                    f.write(chunk)
                            document.pdf_file = os.path.join("documents/pdf", pdf_filename)
                            document.save()

                            # Save PDF file to PublicFile
                            public_pdf_file = PublicFile(
                                tenant=request.tenant,
                                original_name=pdf_filename,
                                file=os.path.join("documents/pdf", pdf_filename),
                                folder=template_folder,
                                created_by=user
                            )
                            public_pdf_file.save()

                            print("Sending email for uploaded PDF")
                            send_approval_request(document)
                            continue

                    pdf_filename = f"{base_filename}.pdf"
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

                        print("LibreOffice stdout:", result.stdout.decode())
                        print("LibreOffice stderr:", result.stderr.decode())

                        # Confirm output PDF file path
                        if os.path.exists(absolute_pdf_path):
                            document.pdf_file = relative_pdf_path
                            document.save()

                            # Save PDF file to PublicFile
                            public_pdf_file = PublicFile(
                                tenant=request.tenant,
                                original_name=pdf_filename,
                                file=relative_pdf_path,
                                folder=template_folder,
                                created_by=user
                            )
                            public_pdf_file.save()
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
        else:
            print("Formset errors:", formset.errors)
            print("Non-form errors:", formset.non_form_errors())
    else:
        print("GET request received")
        formset = DocumentFormSet()
    
    return render(request, "documents/create_document.html", {"formset": formset})

@user_passes_test(is_admin)
def users_list(request):
    # Validate that the requesting user belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: User does not belong to the current tenant.")

    # Filter users by the current tenant
    users = CustomUser.objects.filter(tenant=request.tenant).order_by('date_joined')
    paginator = Paginator(users, 10)  # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "users/users_list.html", {"users": page_obj})

@user_passes_test(is_admin)
def approve_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to the current tenant.")

    # Get the user, ensuring they belong to the same tenant
    try:
        user = CustomUser.objects.get(id=user_id, tenant=request.tenant)
    except CustomUser.DoesNotExist:
        return HttpResponseForbidden("User not found or does not belong to your tenant.")

    # Activate the user
    user.is_active = True
    user.save()

    # Use the admin's email credentials (request.user is already the admin)
    admin_user = request.user
    sender_email = admin_user.smtp_email
    sender_password = admin_user.smtp_password

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    # Set up email connection
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host="smtp.zoho.com",
        port=587,
        username=sender_email,
        password=sender_password,
        use_tls=True,
    )

    # Generate tenant-specific login URL
    # Determine base domain based on environment
    if settings.DEBUG:
        base_domain = "127.0.0.1:8000"  # Local development
        protocol = "http"
    else:
        base_domain = "teammanager.ng"  # Production
        protocol = "https"

    # Generate tenant-specific login URL
    login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/login"

    # Prepare email
    subject = f"Account Approval: {user.username}"
    message = f"""
    Dear {user.username},

    Your account has been activated. Please click the link below to log in:
    {login_url}

    Best regards,  
    {admin_user.get_full_name() or admin_user.username}
    """

    print("Sending mail...")

    try:
        # Send email to the user
        send_mail(
            subject,
            message,
            sender_email,
            [user.email],
            connection=connection,
        )
    except Exception as e:
        print(f"Failed to send email: {e}")
        return HttpResponseForbidden("Failed to send approval email. Contact admin.")

    return redirect("users_list")

def account_activation_sent(request):
    return render(request, "registration/account_activation_sent.html")

@user_passes_test(is_admin)
def edit_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to the current tenant.")

    # Get the user, ensuring they belong to the same tenant
    user = get_object_or_404(CustomUser, id=user_id, tenant=request.tenant)

    if request.method == "POST":
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            # Ensure the tenant field cannot be changed
            form.instance.tenant = request.tenant
            form.save()
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(CustomUser).pk,
                object_id=user.id,
                object_repr=user.username,
                action_flag=CHANGE,
                change_message='Edited user profile'
            )
            return redirect("users_list")
    else:
        form = UserForm(instance=user)
    return render(request, "users/edit_user.html", {"form": form})


def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.is_active = False
            user.tenant = request.tenant
            if not request.tenant:
                return HttpResponseForbidden("No tenant associated with this request.")
            user.save()

            # Send confirmation email
            admin_user = CustomUser.objects.filter(
                tenant=request.tenant, roles__name="Admin"
            ).first()
            if admin_user:
                sender_email = admin_user.smtp_email
                sender_password = admin_user.smtp_password
                if sender_email and sender_password:
                    connection = get_connection(
                        backend="django.core.mail.backends.smtp.EmailBackend",
                        host="smtp.zoho.com",
                        port=587,
                        username=sender_email,
                        password=sender_password,
                        use_tls=True,
                    )
                    base_domain = "127.0.0.1:8000" if settings.DEBUG else "teammanager.ng"
                    protocol = "http" if settings.DEBUG else "https"
                    login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/login"
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
                        # Log error or notify admin, but proceed with registration
            return redirect("account_activation_sent")
    else:
        form = SignUpForm()
    return render(request, "registration/register.html", {"form": form})

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to the current tenant.")

    # Get the user, ensuring they belong to the same tenant
    user = get_object_or_404(CustomUser, id=user_id, tenant=request.tenant)

    # Prevent admins from deleting themselves
    if user == request.user:
        return HttpResponseForbidden("You cannot delete your own account.")

    user.delete()
    return redirect("users_list")

@login_required
def document_list(request):
    # Validate that the user belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: User does not belong to the current tenant.")

    # Start with documents filtered by the current tenant
    documents = Document.objects.filter(tenant=request.tenant)

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
        documents = documents.filter(created_by__username__iexact=created_by, created_by__tenant=request.tenant)
        print(f"Filtering by created_by: {created_by}")
    if approved_by:
        documents = documents.filter(approved_by__username__iexact=approved_by, approved_by__tenant=request.tenant)
        print(f"Filtering by approved_by: {approved_by}")
    if send_email:
        email_sent = send_email.lower() == 'sent'
        documents = documents.filter(email_sent=email_sent)
        print(f"Filtering by email_sent: {email_sent}")

    # Paginate filtered documents
    paginator = Paginator(documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get distinct values for filter dropdowns, scoped to the tenant
    distinct_companies = Document.objects.filter(tenant=request.tenant).values_list('company_name', flat=True).distinct()
    distinct_type = Document.objects.filter(tenant=request.tenant).values_list('document_type', flat=True).distinct()
    distinct_created_by = CustomUser.objects.filter(
        tenant=request.tenant,
        id__in=Document.objects.filter(tenant=request.tenant).values_list('created_by', flat=True).distinct()
    ).values_list('username', flat=True)
    distinct_approved_by = CustomUser.objects.filter(
        tenant=request.tenant,
        id__in=Document.objects.filter(tenant=request.tenant).values_list('approved_by', flat=True).distinct()
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
    return render(request, "home.html")


@login_required
def approve_document(request, document_id):
    # Ensure the user belongs to the current tenant
    if not hasattr(request, 'tenant') or not request.user.tenant == request.tenant:
        return HttpResponseForbidden("You are not authorized to perform actions for this tenant.")

    # Fetch the document, ensuring it belongs to the current tenant
    document = get_object_or_404(Document, id=document_id, tenant=request.tenant)

    # Restrict approval to users with the BDM role
    if not request.user.roles.filter(name="BDM").exists():
        return HttpResponseForbidden("You are not allowed to approve this document.")

    # Update document status and approved_by
    document.status = "approved"
    document.approved_by = request.user
    document.save()

    # Ensure the BDM has SMTP credentials (or use tenant-specific SMTP settings)
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

    # Ensure the document's creator belongs to the same tenant
    if document.created_by.tenant != request.tenant:
        return HttpResponseForbidden("Invalid document creator for this tenant.")

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

    return redirect("document_list")  # Redirect to tenant-scoped document list

@login_required
def autocomplete_sales_rep(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    if 'term' in request.GET:
        qs = CustomUser.objects.filter(
            tenant = request.tenant,
            roles__name='Sales Rep',
            username__icontains=request.GET.get('term')
        ).distinct()
        names = list(qs.values_list('username', flat=True))
        return JsonResponse(names, safe=False)


def send_approved_email(request, document_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    document = get_object_or_404(Document, id=document_id, tenant=request.tenant)

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
    if not recipient:
        return HttpResponseForbidden("No valid recipient email provided.")

    # recipient = [document.contact_person_email]

    # Get Sales Rep email
    sales_rep_email = CustomUser.objects.filter(username=document.sales_rep, tenant=request.tenant).values_list("email", flat=True)

    # Get all BDM emails
    bdm_emails = CustomUser.objects.filter(roles__name="BDM", tenant=request.tenant).values_list("email", flat=True)

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
    if hasattr(request, 'tenant') and request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized to perform actions for this tenant.")
    document = get_object_or_404(Document, id=document_id, tenant=request.tenant)

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
    if hasattr(request, 'tenant') and request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized to perform actions for this tenant.")
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You must be logged in to upload images.")
    logger.info(f"User {request.user.username} uploading image to CKEditor")
    response = ckeditor_upload(request)
    if response.status_code == 200:
        logger.info(f"Image upload successful for user {request.user.username}")
    else:
        logger.error(f"Image upload failed for user {request.user.username}: {response.content}")
    return response

@login_required
def create_from_editor(request):
    # Validate that the user belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: User does not belong to the current tenant.")

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

            # Get or create the "Template Document" folder
            user = request.user
            department = user.department if hasattr(user, 'department') else None
            team = user.teams.first() if hasattr(user, 'teams') and user.teams.exists() else None

            # Ensure user has a department or team
            if not department and not team:
                messages.error(request, "User must be associated with a department or team.")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Choose department or team for the folder (prefer department if available)
            folder_defaults = {
                'created_by': user,
                'department': department,
                'team': team if not department else None
            }

            try:
                template_folder, created = PublicFolder.objects.get_or_create(
                    tenant=request.tenant,
                    name="Template Document",
                    defaults=folder_defaults
                )
            except ValidationError as e:
                print(f"PublicFolder creation error: {e}")
                messages.error(request, f"Error creating Template Document folder: {e}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Validate folder access
            if template_folder.department and template_folder.department != user.department:
                messages.error(request, "Invalid Department for Template Document folder.")
                return render(request, 'documents/create_from_editor.html', {'form': form})
            if template_folder.team and template_folder.team not in user.teams.all():
                messages.error(request, "Invalid Team for Template Document folder.")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Save the .docx file
            word_filename = f"{slugify(title)}_{request.user.id}_{template_folder.id}.docx"
            word_path = os.path.join(word_dir, word_filename)
            try:
                doc.save(word_path)
                print(f"Saved .docx: {word_path}")
            except Exception as e:
                messages.error(request, f"Error creating .docx file: {e}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Generate and save the .pdf file using LibreOffice
            pdf_filename = f"{slugify(title)}_{request.user.id}_{template_folder.id}.pdf"
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
                abs_word_path = os.path.abspath(word_path)
                abs_output_dir = os.path.dirname(os.path.abspath(absolute_pdf_path))

                # Run LibreOffice to convert .docx to .pdf
                result = subprocess.run(
                    [libreoffice_path, "--headless", "--convert-to", "pdf", "--outdir", abs_output_dir, abs_word_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=30
                )

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

            # Save to PublicFile
            try:
                public_word_file = PublicFile(
                    tenant=request.tenant,
                    original_name=word_filename,
                    file=os.path.join("documents/word", word_filename),
                    folder=template_folder,
                    created_by=user
                )
                public_word_file.save()

                public_pdf_file = PublicFile(
                    tenant=request.tenant,
                    original_name=pdf_filename,
                    file=relative_pdf_path,
                    folder=template_folder,
                    created_by=user
                )
                public_pdf_file.save()
            except Exception as e:
                print(f"Error saving to PublicFile: {e}")
                messages.error(request, f"Error saving files to public storage: {e}")
                return render(request, 'documents/create_from_editor.html', {'form': form})

            # Save to Document
            document = Document(
                document_type='Uploaded',
                document_source='editor',
                company_name='N/A',
                company_address='N/A',
                contact_person_name='N/A',
                contact_person_email='N/A',
                contact_person_designation='N/A',
                sales_rep='N/A',
                created_by=request.user,
                tenant=request.tenant,
                word_file=os.path.join("documents/word", word_filename),
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
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, id=parent_id, created_by=request.user, tenant=request.tenant)

    folders = Folder.objects.filter(created_by=request.user, parent=parent, tenant=request.tenant)
    files = File.objects.filter(folder=parent, uploaded_by=request.user, tenant=request.tenant)

    folder_form = FolderForm(initial={'parent': parent})
    file_form = FileUploadForm()

    return render(request, 'folder/folder_list.html', {
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
            folder.tenant = request.tenant
            # Validate that the user belongs to the same tenant
            if folder.created_by.tenant != request.tenant:
                return HttpResponse("Unauthorized: User does not belong to the current tenant.", status=403)
            parent_id = request.POST.get('parent')
            if parent_id:
                folder.parent = Folder.objects.get(id=parent_id, tenant=request.tenant)
            folder.save()
            return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def delete_folder(request, folder_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    folder = get_object_or_404(Folder, id=folder_id, created_by=request.user, tenant=request.tenant)
    folder.delete()
    return JsonResponse({'success': True})
    # return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.save(commit=False)
            uploaded_file.uploaded_by = request.user
            uploaded_file.original_name = request.FILES['file'].name
            uploaded_file.tenant = request.tenant
            if uploaded_file.uploaded_by.tenant != request.tenant:
                return HttpResponse("Unauthorized: User does not belong to the current tenant.", status=403)
            uploaded_file.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def delete_file(request, file_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user, tenant=request.tenant)
    file.delete()
    return JsonResponse({'success': True})
    # return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
def rename_folder(request, folder_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    folder = get_object_or_404(Folder, id=folder_id, created_by=request.user, tenant=request.tenant)
    if request.method == 'POST':
        new_name = request.POST.get('name', '').strip()

        # Validate the new name
        if not new_name:
            return JsonResponse({'success': False, 'error': 'Folder name cannot be empty.'}, status=400)

        if len(new_name) > 255:
            return JsonResponse({'success': False, 'error': 'Folder name is too long.'}, status=400)

        # Validate name format (e.g., no special characters)
        if not re.match(r'^[\w\s\-\.]+$', new_name):
            return JsonResponse({'success': False, 'error': 'Folder name contains invalid characters.'}, status=400)

        # Check for duplicate folder names within the tenant
        if Folder.objects.filter(tenant=request.tenant, name=new_name).exclude(id=folder.id).exists():
            return JsonResponse({'success': False, 'error': 'A folder with this name already exists.'}, status=400)

        try:
            with transaction.atomic():
                folder.name = new_name
                folder.save()
                return JsonResponse({'success': True, 'new_name': folder.name})
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)


@login_required
def rename_file(request, file_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user, tenant=request.tenant)
    if request.method == 'POST':
        new_name = request.POST.get('name')
        # Validate the new name
        if not new_name:
            return JsonResponse({'success': False, 'error': 'File name cannot be empty.'}, status=400)

        if len(new_name) > 255:
            return JsonResponse({'success': False, 'error': 'File name is too long.'}, status=400)

        # Validate name format (e.g., no special characters)
        if not re.match(r'^[\w\s\-\.]+$', new_name):
            return JsonResponse({'success': False, 'error': 'File name contains invalid characters.'}, status=400)

        try:
            with transaction.atomic():
                file.original_name = new_name
                file.save()
                return JsonResponse({'success': True, 'new_name': file.original_name})
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)

@login_required
def move_folder(request, folder_id):
    if not hasattr (request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    folder = get_object_or_404(Folder, id=folder_id, created_by=request.user, tenant=request.tenant)
    if request.method == 'POST':
        new_parent_id = request.POST.get('new_parent_id')
        if new_parent_id:
            folder.parent = Folder.objects.get(id=new_parent_id, tenant=request.tenant)
            folder.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@login_required
def move_file(request, file_id):
    if not hasattr (request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")
    file = get_object_or_404(File, id=file_id, uploaded_by=request.user, tenant=request.tenant)
    if request.method == 'POST':
        new_folder_id = request.POST.get('new_folder_id')
        if new_folder_id:
            file.folder = Folder.objects.get(id=new_folder_id, tenant=request.tenant)
            file.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)
# Tasks
@login_required
def create_task(request):
    # Ensure the user belongs to the current tenant
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        return HttpResponseForbidden("You are not authorized for this tenant.")

    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.tenant = request.user.tenant
            task.save()
            form.save_m2m()
            return redirect('task_list')
    else:
        form = TaskForm(user=request.user)

    return render(request, 'tasks/create_task.html', {'form': form})


@login_required
def task_list(request):
    # Validate tenant access
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")

    category = request.GET.get('category', 'overall')
    
    # Filter tasks by tenant and user (assigned_to or created_by)
    tasks = Task.objects.filter(
        Q(assigned_to=request.user) | Q(created_by=request.user),
        tenant=request.tenant
    ).distinct()
    
    # Apply category-specific filtering
    if category == 'personal':
        tasks = tasks.filter(assigned_to=request.user, created_by=request.user)
    elif category == 'corporate':
        tasks = tasks.filter(assigned_to=request.user).exclude(created_by=request.user)
    
    # Update overdue tasks for the current tenant
    overdue_tasks = Task.objects.filter(
        tenant=request.tenant,
        due_date__lt=date.today(),
        status__in=['pending', 'in_progress', 'on_hold'],
        assigned_to=request.user
    )
    if overdue_tasks.exists():
        logger.debug(f"Updating {overdue_tasks.count()} overdue tasks for tenant {request.tenant}")
        overdue_tasks.update(status='overdue')

    # Filter users by tenant and optionally by department
    users = CustomUser.objects.filter(tenant=request.tenant)
    if request.user.department:
        users = users.filter(department=request.user.department)
    
    logger.debug(f"Task list for tenant {request.tenant}: {tasks.count()} tasks, {users.count()} users")

    context = {
        'tasks': tasks,
        'status_labels': Task.STATUS_CHOICES,
        'today': date.today(),
        'user': request.user,
        'users': users,
        'category': category,
    }
    return render(request, 'tasks/task_list.html', context)

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id, tenant=request.tenant)
    if not (task.assigned_to == request.user or task.created_by == request.user or request.user.is_hod()):
        return render(request, 'tasks/error.html', {'message': 'Access denied.'})
    return render(request, 'tasks/task_detail.html', {'task': task})

@csrf_exempt
@login_required
def update_task_status(request, task_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.") 
    task = get_object_or_404(Task, id=task_id, tenant=request.tenant)
    if not (task.assigned_to == request.user or task.created_by == request.user or request.user.is_hod()):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            if new_status in dict(Task.STATUS_CHOICES):
                task.status = new_status
                if new_status == 'completed':
                    task.completed_at = timezone.now()
                task.tenant = request.tenant
                task.save()
                return JsonResponse({'success': True, 'status': task.status})
            return JsonResponse({'error': 'Invalid status'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def reassign_task(request, task_id):
    # Fetch the task, ensuring it belongs to the current tenant
    task = get_object_or_404(Task, id=task_id, tenant=request.tenant)

    # Check permissions: only the task creator or HOD can reassign
    if not (task.created_by == request.user or request.user.is_hod()):
        return JsonResponse({'error': 'Access denied.'}, status=403)

    if request.method == 'POST':
        try:
            # Extract data from POST request
            assigned_to_id = request.POST.get('assigned_to')
            due_date = request.POST.get('due_date')
            if not assigned_to_id:
                return JsonResponse({'error': 'Assigned user is required.'}, status=400)
            
            if not due_date:
                return JsonResponse({'error': 'Due date is required.'}, status=400)

            # Parse due date
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            if due_date < date.today():
                return JsonResponse({'error': 'Due date cannot be in the past.'}, status=400)

            # Fetch the user to assign the task to, ensuring they belong to the same tenant
            from django.contrib.auth import get_user_model
            CustomUser = get_user_model()
            try:
                assigned_user = CustomUser.objects.get(id=assigned_to_id, tenant=request.tenant)
            except CustomUser.DoesNotExist:
                return JsonResponse({'error': 'Invalid user selected.'}, status=400)

            # Update the task
            if task.due_date != due_date:
                task.due_date = due_date
            task.assigned_to = assigned_user
            task.status = 'in_progress'
            task.save()

            return JsonResponse({'success': True, 'message': 'Task reassigned successfully.'})
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': 'An error occurred while reassigning the task.'}, status=500)

    return JsonResponse({'error': 'Invalid request method.'}, status=405)

@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, tenant=request.tenant)
    if not (task.created_by == request.user or request.user.is_hod()):
        return render(request, 'tasks/error.html', {'message': 'Access denied.'})
    
    if request.method == 'POST':
        task.delete()
        return redirect('task_list')
    return render(request, 'tasks/confirm_delete.html', {'task': task})

@login_required
def task_edit(request, task_id):
    # Validate tenant access
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")

    # Fetch task with tenant filter
    task = get_object_or_404(Task, id=task_id, tenant=request.user.tenant)

    # Check access permissions
    if not (task.created_by == request.user or request.user.is_hod()):
        logger.warning(f"Access denied for user {request.user.username} on task {task_id}")
        return render(request, 'tasks/error.html', {'message': 'Access denied.'})
    
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=task, user=request.user)
        if form.is_valid():
            form.instance.tenant = request.tenant
            form.save()
            logger.info(f"Task {task.id} edited by {request.user.username} in tenant {request.tenant}")
            return redirect('task_detail', task_id=task.id)
        
    else:
        form = TaskForm(instance=task, user=request.user)
        logger.debug(f"TaskForm initialized for task {task_id} with tenant: {request.tenant}")

    return render(request, 'tasks/edit_task.html', {'form': form, 'task': task})

@login_required
def delete_task_document(request, task_id, file_id):
    task = get_object_or_404(Task, id=task_id, tenant=request.tenant)
    document = get_object_or_404(File, id=file_id, tenant=request.tenant)
    if not (task.created_by == request.user or request.user.is_hod()) or document not in task.documents.all():
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        task.documents.remove(document)
        if not task.documents.exists():
            document.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def performance_dashboard(request):
    # Validate tenant access
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")

    user = request.user
    category = request.GET.get('category', 'overall')
    
    # Filter tasks by tenant and assigned_to user
    tasks = Task.objects.filter(tenant=request.user.tenant, assigned_to=user)
    if category == 'personal':
        tasks = tasks.filter(created_by=user)
    elif category == 'corporate':
        tasks = tasks.exclude(created_by=user)
    
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago = now - timedelta(days=365)

    weekly_completed = tasks.filter(status='completed', completed_at__gte=week_ago).count()
    monthly_completed = tasks.filter(status='completed', completed_at__gte=month_ago).count()
    yearly_completed = tasks.filter(status='completed', completed_at__gte=year_ago).count()

    overdue_tasks = tasks.filter(status='overdue', due_date__lt=now).count()

    performance_score = completion_percentage - (overdue_tasks * 10)
    performance_score = max(0, min(100, performance_score))

    context = {
        'category': category,
        'completion_percentage': round(completion_percentage, 2),
        'weekly_completed': weekly_completed,
        'monthly_completed': monthly_completed,
        'yearly_completed': yearly_completed,
        'overdue_tasks': overdue_tasks,
        'performance_score': round(performance_score, 2),
    }
    return render(request, 'dashboard/performance_dashboard.html', context)

@login_required
def hod_performance_dashboard(request):
    # Validate tenant access
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    user = request.user
    if not user.is_hod():
        return render(request, 'tasks/error.html', {'message': 'Access denied. HOD role required.'})

    department = user.department
    if not department:
        return render(request, 'tasks/error.html', {'message': 'No department assigned.'})

    department_users = CustomUser.objects.filter(department=department, tenant=request.tenant).select_related('department')
    users_ids = [u.id for u in department_users]

    # Get user_id from query parameter (optional)
    selected_user_id = request.GET.get('user_id', 'all')
    
    # Base query: corporate tasks (created by department members, not personal)
    tasks = Task.objects.filter(created_by__in=users_ids, tenant=request.tenant).exclude(created_by=F('assigned_to')).select_related('created_by', 'assigned_to')

    # Filter by selected user if specified
    if selected_user_id != 'all':
        tasks = tasks.filter(assigned_to_id=selected_user_id)

    # Department-wide or user-specific metrics
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Per-user metrics for the table
    user_metrics = []
    for dept_user in department_users:
        user_tasks = Task.objects.filter(
            created_by__in=users_ids,
            assigned_to=dept_user,
            tenant=request.tenant
        ).exclude(created_by=F('assigned_to')).select_related('assigned_to')
        user_total_tasks = user_tasks.count()
        user_completed_tasks = user_tasks.filter(status='completed').count()
        user_completion_percentage = (user_completed_tasks / user_total_tasks * 100) if user_total_tasks > 0 else 0
        user_metrics.append({
            'user_id': dept_user.id,
            'full_name': dept_user.get_full_name() or dept_user.username,
            'total_tasks': user_total_tasks,
            'completed_tasks': user_completed_tasks,
            'completion_percentage': round(user_completion_percentage, 2),
        })

    context = {
        'department': department.name,
        'completion_percentage': round(completion_percentage, 2),
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'user_metrics': user_metrics,
        'department_users': department_users,
        'selected_user_id': selected_user_id,
    }
    return render(request, 'dashboard/hod_performance_dashboard.html', context)

@login_required
def view_my_profile(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    profile, created = StaffProfile.objects.get_or_create(user=request.user, tenant=request.tenant)
    visible_fields = [
            "photo",
            "first_name", "last_name", "middle_name", "email", "phone_number", "sex", "date_of_birth", "home_address",
            "state_of_origin", "lga", "religion",
            "institution", "course", "degree", "graduation_year",
            "account_number", "bank_name", "account_name",
            "location", "employment_date", "department", "team", "designation", "official_email",
            "emergency_name", "emergency_relationship", "emergency_phone",
            "emergency_address", "emergency_email",
        ]
    return render(request, "dashboard/my_profile.html", {"profile": profile, "visible_fields": visible_fields})


@login_required
def edit_my_profile(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    profile,_ = StaffProfile.objects.get_or_create(user=request.user, tenant=request.tenant) # staff_profile = request.user.staff_profile  # Assuming one profile per user
    if request.method == 'POST':
        profile_form = StaffProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        
        if profile_form.is_valid():
            profile_form.save()
            return redirect('view_my_profile')  # Redirect to profile view or success page
    else:
        profile_form = StaffProfileForm(instance=profile, user=request.user)
        document_form = StaffDocumentForm()
        
    return render(request, 'dashboard/edit_profile.html', {
        'profile': profile,
        'profile_form': profile_form,
        'document_form': document_form,
    })

@login_required
def add_staff_document(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    if request.method == 'POST':
        form = StaffDocumentForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            document = form.save(commit=False)
            document.staff_profile = get_object_or_404(StaffProfile, user=request.user, tenant=request.tenant)
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
    if hasattr(request, 'tenant') and request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    try:
        # Get the user's StaffProfile (assuming one profile per user)
        staff_profile = StaffProfile.objects.get(user=request.user, tenant=request.tenant)
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
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    # Filter staff profiles by tenant
    profiles = StaffProfile.objects.select_related(
        "user", "department"
    ).prefetch_related("team").filter(user__tenant=request.user.tenant)

    # Restrict to department for HODs (optional)
    if request.user.is_hod() and not is_admin(request.user):
        profiles = profiles.filter(department=request.user.department)

    logger.debug(f"Profiles found: {profiles.count()}")

    # Grouping by Department → Team (Tenant is already scoped)
    grouped = {}
    for profile in profiles:
        dept = profile.department.name if profile.department else "No Department"
        teams = profile.team.all()
        if not teams:
            teams = [None]
        for team in teams:
            team_name = team.name if team else "No Team"
            grouped.setdefault(dept, {}).setdefault(team_name, []).append(profile)

    logger.debug(f"Grouped dictionary: {grouped}")
    return render(request, "staff/staff_directory.html", {"grouped": grouped})


@login_required
def view_staff_profile(request, user_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    profile = get_object_or_404(StaffProfile, user_id=user_id, tenant=request.tenant)

    # Ensure the profile belongs to the same tenant as the requesting user
    if profile.user.tenant != request.user.tenant:
        return render(request, "403.html", status=403)

    viewer = StaffProfile.objects.filter(user=request.user, tenant=request.tenant).first()

    visible_fields = [
        "photo",
        "first_name", "last_name", "middle_name", "email", "phone_number", "sex", "date_of_birth", "home_address",
        "state_of_origin", "lga", "religion",
        "institution", "course", "degree", "graduation_year",
        "account_number", "bank_name", "account_name",
        "location", "employment_date",
        "department", "team", "designation", "official_email",
        "emergency_name", "emergency_relationship", "emergency_phone",
        "emergency_address", "emergency_email",
    ]

    # Visibility logic based on shared department/team (within same tenant already)
    if viewer:
        if profile.department == viewer.department:
            visible_fields += ["department"]
            shared_teams = set(profile.team.values_list("id", flat=True)) & set(viewer.team.values_list("id", flat=True))
            if shared_teams:
                visible_fields += ["team"]

    return render(request, "staff/view_staff_profile.html", {
        "profile": profile,
        "viewer": viewer,
        "visible_fields": visible_fields,
    })

def staff_list(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")
    
    # Get query parameters
    sort_by = request.GET.get('sort_by', 'name')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '')
    filter_dept = request.GET.get('dept', '')
    page = request.GET.get('page', 1)

    # Base queryset: only staff from the same tenant
    profiles = StaffProfile.objects.select_related(
        'user', 'department'
    ).prefetch_related('team').filter(user__tenant=request.user.tenant)

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

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    profiles = profiles.order_by(sort_field)

    # Pagination
    paginator = Paginator(profiles, 10)  # 10 profiles per page
    page_obj = paginator.get_page(page)

    # Filter dropdown: restrict departments to the tenant only
    departments = Department.objects.filter(
        staff__user__tenant=request.user.tenant
    ).distinct()

    context = {
        'profiles': page_obj,
        'departments': departments,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'search_query': search_query,
        'filter_dept': filter_dept,
    }
    return render(request, 'staff/staff_list.html', context)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification, UserNotification
from django.utils.timezone import now

@login_required
def notifications_view(request):
    # Validate tenant access
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this tenant.")

    # Filter notifications by tenant and active status
    all_notifications = Notification.objects.filter(
        tenant=request.user.tenant,
        is_active=True
    )

    # Ensure UserNotification exists for each active notification
    active_notifications = []
    for notification in all_notifications:
        user_notification, created = UserNotification.objects.get_or_create(
            user=request.user,
            notification=notification,
            defaults={'seen_at': timezone.now(), 'dismissed': False}
        )
        if not user_notification.dismissed:
            active_notifications.append(user_notification)

    # Get dismissed notifications for the user and tenant
    dismissed_notifications = UserNotification.objects.filter(
        user=request.user,
        notification__tenant=request.user.tenant,
        dismissed=True
    ).select_related('notification').order_by('-seen_at')

    return render(request, 'users/notifications.html', {
        'active_notifications': active_notifications,
        'dismissed_notifications': dismissed_notifications
    })

@require_POST
@login_required
def dismiss_notification(request):
    notification_id = request.POST.get('notification_id')
    try:
        notification = Notification.objects.get(id=notification_id, tenant=request.user.tenant)
        user_notification, created = UserNotification.objects.get_or_create(
            tenant=request.user.tenant,
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
            tenant=request.user.tenant,
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
    user = CustomUser.objects.get(username=request.user.username, tenant=request.user.tenant)
    if request.method == 'POST':
        email_config_form = EmailConfigForm(request.POST, instance=user)
        if email_config_form.is_valid():
            email_config_form.save()
            return redirect('view_my_profile')
    else:
        email_config_form = EmailConfigForm(instance=user)
    return render(request, 'users/email_config.html', {'email_config_form': email_config_form})

from django.db import models
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Event.objects.filter(
            models.Q(created_by=user) | models.Q(participants__user=user),
            tenant=user.tenant
        ).distinct()

    def perform_create(self, serializer):
        print(f"Received data: {self.request.data}")
        event = serializer.save(created_by=self.request.user, tenant=self.request.user.tenant)

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
    CustomUser = get_user_model()
    # if request.user.is_authenticated:
    #     auth_token = Token.objects.get(user=request.user).key if Token.objects.filter(user=request.user).exists() else None
    context = {
        # 'auth_token': auth_token or '',
        'csrf_token': get_token(request),
        'notification_bar_items': [],
        'birthday_others': [],
        'birthday_self': False,
        'users': CustomUser.objects.filter(tenant=request.user.tenant),
    }
    print(f"Context: {context}")  # Debug
    return render(request, 'users/calendar.html', context)

@require_POST
def export_staff_csv(request):
    profile_ids = request.POST.getlist('profile_ids')
    if not profile_ids:
        return HttpResponse(
            status=400,
            content_type='application/json',
            content='{"error": "No profiles selected"}'
        )

    # Only export profiles that belong to the same tenant as the requester
    profiles = StaffProfile.objects.filter(
        user__id__in=profile_ids,
        user__tenant=request.user.tenant
    ).select_related('user', 'department').prefetch_related('team')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="staff_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Phone Number', 'Email', 'Sex', 'Designation', 'Department', 'Team'])

    for profile in profiles:
        writer.writerow([
            f"{profile.first_name} {profile.middle_name or ''} {profile.last_name}".strip(),
            profile.phone_number or 'N/A',
            profile.email or 'N/A',
            profile.sex or 'N/A',
            profile.designation or 'N/A',
            profile.department.name if profile.department else 'N/A',
            ', '.join(profile.team.all().values_list('name', flat=True)) or 'N/A',
        ])

    return response

# Public Folder Views
@login_required
def public_folder_list(request, public_folder_id=None):
    user = request.user
    parent_public_folder = get_object_or_404(PublicFolder, id=public_folder_id, tenant=user.tenant) if public_folder_id else None

    public_folders = PublicFolder.objects.filter(
        Q(department=user.department) | Q(team__in=user.teams.all()),
        parent=parent_public_folder,
        tenant=user.tenant
    ).distinct()

    public_files = PublicFile.objects.filter(
        Q(folder=parent_public_folder) &
        (Q(folder__department=user.department) | Q(folder__team__in=user.teams.all())), tenant=user.tenant
    ).distinct()

    context = {
        'parent': parent_public_folder,
        'public_folders': public_folders,
        'public_files': public_files,
        'folder_form': PublicFolderForm(),
        'file_form': PublicFileForm(),
    }
    return render(request, 'folder/public_folder_list.html', context)

@login_required
@require_POST
def create_public_folder(request):
    form = PublicFolderForm(request.POST)
    if form.is_valid():
        folder = form.save(commit=False)
        folder.created_by = request.user
        user = request.user

        if folder.department and folder.department != user.department:
            # return JsonResponse({'success': False, 'errors': {'department': ['Invalid department']}}, status=403)
            return render(request, 'folder/error.html', {'message': 'Invalid Department.'})
        if folder.team and folder.team not in user.teams.all():
            return JsonResponse({'success': False, 'errors': {'team': ['Invalid team']}}, status=403)
        if folder.parent and not (folder.parent.department == user.department or folder.parent.team in user.teams.all()):
            return JsonResponse({'success': False, 'errors': {'parent': ['No access to parent folder']}}, status=403)

        try:
            folder.save()
            return JsonResponse({'success': True, 'folder_id': folder.id})
        except ValidationError as e:
            return JsonResponse({'success': False, 'errors': {'name': [str(e)]}}, status=400)
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@login_required
@require_POST
def rename_public_folder(request, folder_id):
    folder = get_object_or_404(PublicFolder, id=folder_id, tenant=request.tenant)
    if folder.created_by != request.user:
        return JsonResponse({'success': False, 'errors': {'name': ['You can only rename your own folders']}}, status=403)
    name = request.POST.get('name')
    if not name:
        return JsonResponse({'success': False, 'errors': {'name': ['Name is required']}}, status=400)
    folder.name = name
    folder.save()
    return JsonResponse({'success': True})

@login_required
@require_POST
def move_public_folder(request, folder_id):
    folder = get_object_or_404(PublicFolder, id=folder_id, tenant=request.tenant)
    if folder.created_by != request.user:
        return JsonResponse({'success': False, 'errors': {'new_parent_id': ['You can only move your own folders']}}, status=403)
    new_parent_id = request.POST.get('new_parent_id')
    user = request.user
    if new_parent_id:
        new_parent = get_object_or_404(PublicFolder, id=new_parent_id, tenant=request.tenant)
        if not (new_parent.department == user.department or new_parent.team in user.teams.all()):
            return JsonResponse({'success': False, 'errors': {'new_parent_id': ['No access to destination']}}, status=403)
        if new_parent == folder or new_parent in folder.subfolders.all():
            return JsonResponse({'success': False, 'errors': {'new_parent_id': ['Invalid destination']}}, status=400)
        folder.parent = new_parent
    else:
        folder.parent = None
    folder.save()
    return JsonResponse({'success': True})

@login_required
@require_POST
def delete_public_folder(request, folder_id):
    folder = get_object_or_404(PublicFolder, id=folder_id, tenant=request.tenant)
    if folder.created_by != request.user:
        return JsonResponse({'success': False, 'errors': {'folder': ['You can only delete your own folders']}}, status=403)
    folder.delete()
    return JsonResponse({'success': True})

@login_required
@require_POST
def upload_public_file(request):
    form = PublicFileForm(request.POST, request.FILES)
    if form.is_valid():
        file = form.save(commit=False)
        file.created_by = request.user
        file.original_name = request.FILES['file'].name
        file.tenant = request.tenant
        public_folder_id = request.POST.get('folder')
        if public_folder_id:
            public_folder = get_object_or_404(PublicFolder, id=public_folder_id, tenant=request.tenant)
            user = request.user
            if not (public_folder.department == user.department or public_folder.team in user.teams.all()):
                return JsonResponse({'success': False, 'errors': {'folder': ['No access to folder']}}, status=403)
            file.folder = public_folder
        file.save()
        return JsonResponse({'success': True, 'file_id': file.id})
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
def rename_public_file(request, file_id):
    file = get_object_or_404(PublicFile, id=file_id, tenant=request.tenant)
    if file.created_by != request.user:
        return JsonResponse({'success': False, 'errors': {'name': ['You can only rename your own files']}}, status=403)
    name = request.POST.get('name')
    if not name:
        return JsonResponse({'success': False, 'errors': {'name': ['Name is required']}}, status=400)
    file.original_name = name
    file.save()
    return JsonResponse({'success': True})

@login_required
@require_POST
def move_public_file(request, file_id):
    file = get_object_or_404(PublicFile, id=file_id, tenant=request.tenant)
    if file.created_by != request.user:
        return JsonResponse({'success': False, 'errors': {'new_folder_id': ['You can only move your own files']}}, status=403)
    new_folder_id = request.POST.get('new_folder_id')
    user = request.user
    if new_folder_id:
        new_folder = get_object_or_404(PublicFolder, id=new_folder_id, tenant=request.tenant)
        if not (new_folder.department == user.department or new_folder.team in user.teams.all()):
            return JsonResponse({'success': False, 'errors': {'new_folder_id': ['No access to destination']}}, status=403)
        file.folder = new_folder
    else:
        file.folder = None
    file.save()
    return JsonResponse({'success': True})

@login_required
@require_POST
def delete_public_file(request, file_id):
    file = get_object_or_404(PublicFile, id=file_id, tenant=request.tenant)
    if file.created_by != request.user:
        return JsonResponse({'success': False, 'errors': {'file': ['You can only delete your own files']}}, status=403)
    file.delete()
    return JsonResponse({'success': True})