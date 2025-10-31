from django.contrib.auth.decorators import user_passes_test, login_required
from documents.models import Department, CustomUser
from documents.forms import AssignUsersToDepartmentForm, DepartmentForm
from ..rba_decorators import is_admin 
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages


def assign_users_to_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    tenant = department.tenant

    if request.method == 'POST':
        form = AssignUsersToDepartmentForm(request.POST, tenant=tenant)
        if form.is_valid():
            users = form.cleaned_data['users']
            for user in users:
                user.department = department
                user.save()
            messages.success(request, f"Users successfully assigned to {department.name}.")
            return redirect('department_list')
    else:
        form = AssignUsersToDepartmentForm(tenant=tenant)
    
    return render(request, 'admin/assign_users_to_department.html', {
        'form': form,
        'department': department,
    })

def department_members(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    members = CustomUser.objects.filter(department=department)
    return render(request, 'admin/department_members.html', {'department': department, 'members': members})

@user_passes_test(is_admin)
def department_list(request):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")
    
    # Fetch all departments in that tenant
    departments = Department.objects.filter(tenant=request.tenant)
    paginator = Paginator(departments, 10)  # 10 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, "admin/department_list.html", {"departments": page_obj})

@user_passes_test(is_admin)
def create_department(request):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    if request.method == "POST":
        form = DepartmentForm(request.POST, user=request.user)
        if form.is_valid():
            department = form.save(commit=False)
            department.tenant = request.tenant
            department.save()
            department.hod.department = department
            department.hod.save()
            return redirect("department_list")
    else:
        form = DepartmentForm(user=request.user)
    return render(request, "admin/create_department.html", {"form": form})

@user_passes_test(is_admin)
def edit_department(request, department_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the department, ensuring it belongs to the same tenant
    department = get_object_or_404(Department, id=department_id, tenant=request.tenant)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department, user=request.user)
        if form.is_valid():
            department=form.save(commit=False)
            department.hod.department = department
            department.hod.save()
            department.save()
            return redirect("department_list")
    else:
        form = DepartmentForm(instance=department, user=request.user)
    return render(request, "admin/edit_department.html", {"form": form})

@user_passes_test(is_admin)
def delete_department(request, department_id):
    # Validate that the admin belongs to the current tenant
    if request.user.tenant != request.tenant:
        return HttpResponseForbidden("Unauthorized: Admin does not belong to this company.")

    # Get the department, ensuring it belongs to the same tenant
    department = get_object_or_404(Department, id=department_id, tenant=request.tenant)
    department.delete()
    return redirect("department_list")