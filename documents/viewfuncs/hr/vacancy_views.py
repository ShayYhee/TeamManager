from datetime import timezone
import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from documents.forms import VacancyForm
from documents.models import Vacancy
from ..rba_decorators import is_hr
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator


logger = logging.getLogger(__name__)

@login_required
@user_passes_test(is_hr)
def vacancy_list(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancies = Vacancy.objects.filter(tenant=request.tenant).select_related('created_by', 'updated_by', 'shared_by')
    now = timezone.now()  # Cache for efficiency

    for vacancy in vacancies:
        if vacancy.is_shared and vacancy.share_time and vacancy.share_time <= now:
            if vacancy.share_time_end:
                if now <= vacancy.share_time_end:
                    vacancy.shareable_link = request.build_absolute_uri(vacancy.get_shareable_link())
                else:
                    vacancy.shareable_link = None
                    vacancy.status = "withdrawn"
            else:
                vacancy.shareable_link = request.build_absolute_uri(vacancy.get_shareable_link())
        else:
            vacancy.shareable_link = None

    paginator = Paginator(vacancies, 10)  # 10 vacancies per page
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    return render(request, 'hr/vacancy_list.html', {'vacancies': page_obj})

@login_required
@user_passes_test(is_hr)
def create_vacancy(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    if request.method == 'POST':
        form = VacancyForm(request.POST)
        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.tenant = request.tenant
            vacancy.created_by = request.user
            vacancy.save()
            return redirect('vacancy_list')
    else:
        form = VacancyForm()
    return render(request, 'hr/create_vacancy.html', {'form': form}) 

@login_required
@user_passes_test(is_hr)
def edit_vacancy(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    if request.method == 'POST':
        form = VacancyForm(request.POST, instance=vacancy)
        if form.is_valid():
            form.save(commit=False)
            form.updated_by = request.user
            form.updated_at = timezone.now()
            form.save()
            return redirect('vacancy_list')
    else:
        form = VacancyForm(instance=vacancy)
    return render(request, 'hr/edit_vacancy.html', {'form': form})

@login_required
@user_passes_test(is_hr)
def vacancy_detail(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    
    return render(request, 'hr/vacancy_detail.html', {'vacancy': vacancy})

@login_required
@user_passes_test(is_hr)
def delete_vacancy(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    vacancy.delete()
    return redirect('vacancy_list')

@login_required
@user_passes_test(is_hr)
def share_vacancy(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    if request.method == 'POST':
        end_date = request.POST.get('end_date')
        try:
            share_time_end = timezone.datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
            if share_time_end:
                share_time_end = timezone.make_aware(share_time_end)
        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        vacancy.is_shared = True
        vacancy.status = 'active'
        vacancy.shared_by = request.user
        vacancy.share_time = timezone.now()
        vacancy.share_time_end = share_time_end
        vacancy.save()
        vacancy.shareable_link = request.build_absolute_uri(vacancy.get_shareable_link())
        return JsonResponse({"success": True, "vacancy": vacancy.id, "shareable_link": vacancy.shareable_link})
    
    return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

@login_required
@user_passes_test(is_hr)
def withdraw_vacancy(request, vacancy_id):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        print(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return render(request, 'tenant_error.html', {'error_code': '401','message': 'You are not authorized for this company.'})
    vacancy = get_object_or_404(Vacancy, id=vacancy_id, tenant=request.tenant)
    vacancy.is_shared = False
    vacancy.shared_by = None
    vacancy.share_time = None
    vacancy.share_time_end = None
    vacancy.status = 'withdrawn'
    vacancy.save()
    return JsonResponse({"success": True})

def vacancy_post(request, token):
    vacancy = get_object_or_404(Vacancy, share_token=token)
    if not vacancy.is_shared or (vacancy.share_time_end and timezone.now() > vacancy.share_time_end) or vacancy.status in ['closed', 'withdrawn']:
        message = "This vacancy is no longer available."
        if vacancy.status == 'closed':
            message = "This vacancy is closed."
        elif vacancy.status == 'withdrawn':
            message = "This vacancy is withdrawn."
        return render(request, 'hr/vacancy_expired.html', {'message': message})
    
    return render(request, 'hr/vacancy_post.html', {'vacancy': vacancy})