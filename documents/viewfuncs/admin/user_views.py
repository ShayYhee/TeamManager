from django.contrib.auth.decorators import user_passes_test, login_required
from documents.forms import EditUserForm, UserForm
from documents.models import CustomUser
from documents.viewfuncs.mail_connection import get_email_smtp_connection
from raadaa import settings
from ..rba_decorators import is_admin 
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.admin.models import LogEntry, CHANGE, ADDITION, DELETION
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from ..send_mails import send_user_approved_email

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

@login_required
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

@login_required
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

@login_required
@user_passes_test(is_admin)
# @user_passes_test(lambda u: u.is_superuser)
def approve_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the user, ensuring they belong to the same tenant
    try:
        user = CustomUser.objects.get(id=user_id, tenant=request.tenant)
    except CustomUser.DoesNotExist:
        return HttpResponseForbidden("User not found or does not belong to your company.")

    # Activate the user
    user.is_active = True
    user.save()

    # Send user approved email
    # Use the admin's email credentials (request.user is already the admin)
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

    if not sender_provider or not sender_email or not sender_password:
        return HttpResponseForbidden("Your email credentials are missing. Contact admin.")
    
    send_user_approved_email(request, user, admin_user, sender_provider, sender_email, sender_password)

    return redirect("users_list")

@login_required
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

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the user, ensuring they belong to the same tenant
    user = get_object_or_404(CustomUser, id=user_id, tenant=request.tenant)

    # Prevent admins from deleting themselves
    if user == request.user:
        return HttpResponseForbidden("You cannot delete your own account.")

    user.delete()
    return redirect("users_list")