import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from Raadaa.documents.forms import CompanyDocumentForm, CompanyProfileForm
from Raadaa.documents.models import CompanyProfile
from django.http import HttpResponseForbidden
from rba_decorators import is_admin 
from django.shortcuts import redirect, render

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(is_admin)
def edit_company_profile(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this company.")
    
    company_profile, created = CompanyProfile.objects.get_or_create(
        tenant=request.tenant,
        defaults={'company_name': request.tenant.name}
    )
    
    if request.method == "POST":
        form = CompanyProfileForm(request.POST, request.FILES, instance=company_profile)
        if form.is_valid():
            form.save()
            return redirect("view_company_profile")
    else:
        form = CompanyProfileForm(instance=company_profile)
        document_form = CompanyDocumentForm()
    return render(request, "admin/edit_company_profile.html", {"form": form, 'profile': company_profile, 'document_form': document_form})
