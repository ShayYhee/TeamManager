from django.contrib.auth.decorators import user_passes_test
from documents.models import StaffProfile
from documents.forms import StaffProfileForm
from ..rba_decorators import is_admin 
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render, get_object_or_404
from django.core.paginator import Paginator


@user_passes_test(is_admin)
def staff_profile_list(request):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    staff_profiles = StaffProfile.objects.filter(tenant=request.tenant)
    paginator = Paginator(staff_profiles, 10)  # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "admin/staff_profile_list.html", {"staff_profiles": page_obj})

@user_passes_test(is_admin)
def create_staff_profile(request):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    if request.method == "POST":
        form = StaffProfileForm(request.POST, user=request.user)
        if form.is_valid():
            staff_profile=form.save(commit=False)
            staff_profile.tenant = request.tenant
            staff_profile.save()
            return redirect("staff_profile_list")
    else:
        form = StaffProfileForm(user=request.user)
    return render(request, "admin/create_staff_profile.html", {"form": form})

@user_passes_test(is_admin)
def edit_staff_profile(request, staff_profile_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the event, ensuring it belongs to the same tenant
    staff_profile = get_object_or_404(StaffProfile, id=staff_profile_id, tenant=request.tenant)

    if request.method == "POST":
        form = StaffProfileForm(request.POST, instance=staff_profile, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("staff_profile_list")
    else:
        form = StaffProfileForm(instance=staff_profile, user=request.user)
    return render(request, "admin/edit_staff_profile.html", {"form": form})

@user_passes_test(is_admin)
def delete_staff_profile(request, staff_profile_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the event, ensuring it belongs to the same tenant
    staff_profile = get_object_or_404(StaffProfile, id=staff_profile_id, tenant=request.tenant)
    staff_profile.delete()
    return redirect("staff_profile_list")