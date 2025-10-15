import logging
from django.contrib.auth.decorators import login_required
from Raadaa.documents.models import CompanyProfile, CustomUser, Department, Team
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render


logger = logging.getLogger(__name__)

@login_required
def view_company_profile(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this company.")
    print(f"User tenant: {request.user.tenant}. Request tenant: {request.tenant.name}")
    try: 
        tenant_profile, created = CompanyProfile.objects.get_or_create(
            tenant=request.tenant
        )

        num_staff = CustomUser.objects.filter(tenant=request.tenant).count()
        num_departments = Department.objects.filter(tenant=request.tenant).count()
        num_teams = Team.objects.filter(tenant=request.tenant).count()

        tenant_profile.num_staff = num_staff
        tenant_profile.num_departments = num_departments
        tenant_profile.num_teams = num_teams
        tenant_profile.save()

        depts = Department.objects.filter(tenant=request.tenant)
        teams = Team.objects.filter(tenant=request.tenant)
        return render(request, 'admin/company_profile.html', {'tenant_profile': tenant_profile, 'depts': depts, 'teams': teams})
    except Exception as e:
        logger.error(f"Error in view_company_profile: {e}")
        # return render(request, 'tenant_error.html', {'message': 'An unexpected error occurred'}, status=500)
        return HttpResponse("An unexpected error occurred")