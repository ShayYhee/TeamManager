from django.contrib.auth.decorators import user_passes_test
from Raadaa.documents.forms import EditUserForm, UserForm
from Raadaa.documents.models import CustomUser
from Raadaa.documents.viewfuncs.mail_connection import get_email_smtp_connection
from Raadaa.raadaa import settings
from rba_decorators import is_admin 
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.admin.models import LogEntry, CHANGE, ADDITION, DELETION
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string


main_superuser = CustomUser.objects.filter(is_superuser=True).first()

@user_passes_test(is_admin)
def users_list(request):
    # Validate that the requesting user belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: User does not belong to this company.")

    # Filter users by the current tenant
    users = CustomUser.objects.filter(tenant=request.tenant).order_by('date_joined')
    paginator = Paginator(users, 10)  # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    count = users.count()
    return render(request, "admin/users_list.html", {"users": page_obj, 'count': count})

@user_passes_test(is_admin)
def create_user(request):
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")
    if request.method == "POST":
        form = UserForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.tenant = request.tenant
            user.save()
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(CustomUser).pk,
                object_id=user.id,
                object_repr=user.username,
                action_flag=ADDITION,
                change_message='Created user'
            )
            return redirect("users_list")
    else:
        form = UserForm(tenant=request.tenant)
    return render(request, "admin/create_user.html", {"form": form})

@user_passes_test(is_admin)
def view_user_details(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the user, ensuring they belong to the same tenant
    try:
        user_view = CustomUser.objects.get(id=user_id, tenant=request.tenant)
        details = ['username', 'first_name', 'last_name', 'email', 
                 'is_active', 'roles', 'phone_number', 
                  'department', 'teams', 'email_address', 'email_password']
    except CustomUser.DoesNotExist:
        # return HttpResponseForbidden("User not found or does not belong to your tenant.")
        raise PermissionDenied("User not found or does not belong to your company.")

    return render(request, "admin/view_user_details.html", {"user_view": user_view, "details": details})
@user_passes_test(is_admin)
# # @user_passes_test(lambda u: u.is_superuser)
# def approve_user(request, user_id):
#     # Validate that the admin belongs to the current tenant
#     if request.user.tenant != request.tenant:
#         return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

#     # Get the user, ensuring they belong to the same tenant
#     try:
#         user = CustomUser.objects.get(id=user_id, tenant=request.tenant)
#     except CustomUser.DoesNotExist:
#         return HttpResponseForbidden("User not found or does not belong to your company.")

#     # Activate the user
#     user.is_active = True
#     user.save()

#     # Use the admin's email credentials (request.user is already the admin)
#     admin_user = request.user
#     if admin_user.email_address and admin_user.email_password:
#         sender_provider = admin_user.email_provider
#         sender_email = admin_user.email_address
#         sender_password = admin_user.email_password
#     else:
#         superuser = main_superuser
#         sender_provider = superuser.email_provider
#         sender_email = superuser.email_address
#         sender_password = superuser.email_password

#     if not sender_email or not sender_password:
#         return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

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

#     return redirect("users_list")

def approve_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    try:
        user = CustomUser.objects.get(id=user_id, tenant=request.tenant)
    except CustomUser.DoesNotExist:
        return HttpResponseForbidden("User not found or does not belong to your company.")

    # Activate the user
    user.is_active = True
    user.save()


    admin_user = request.user
    if admin_user.email_address and admin_user.email_password:
        sender_provider = admin_user.email_provider
        sender_email = admin_user.email_address
        sender_password = admin_user.email_password
    else:
        superuser = main_superuser
        sender_provider = superuser.email_provider
        sender_email = superuser.email_address
        sender_password = superuser.email_password

    if not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")

    # Set up email connection
    connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)

    # Generate tenant-specific login URL
    if settings.DEBUG:
        base_domain = "127.0.0.1:8000"  
        protocol = "http"
    else:
        base_domain = "teammanager.ng"  
        protocol = "https"

    login_url = f"{protocol}://{request.tenant.slug}.{base_domain}/accounts/login"

    context = {
        'username': user.username,
        'full_name': user.get_full_name() or user.username,
        'admin_name': admin_user.get_full_name() or admin_user.username,
        'tenant_name': request.tenant.name,
        'login_url': login_url,
        'protocol': protocol,
    }

    html_content = render_to_string('emails/account_approval.html', context)

    subject = f"Account Approved - {request.tenant.name}"

    print("Sending mail...")

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
        
    except Exception as e:
        print(f"Failed to send email: {e}")
        return HttpResponseForbidden("Failed to send approval email. Contact admin.")

    return redirect("users_list")

@user_passes_test(is_admin)
def edit_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the user, ensuring they belong to the same tenant
    user = get_object_or_404(CustomUser, id=user_id, tenant=request.tenant)

    if request.method == "POST":
        form = EditUserForm(request.POST, instance=user, tenant=request.tenant)
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
        form = EditUserForm(instance=user, tenant=request.tenant)
    return render(request, "admin/edit_user.html", {"form": form})
