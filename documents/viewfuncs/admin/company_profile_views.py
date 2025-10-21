import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from documents.forms import CompanyDocumentForm, CompanyProfileForm
from documents.models import CompanyProfile, CompanyDocument, StaffProfile, StaffDocument
from django.http import HttpResponseForbidden, JsonResponse
from ..rba_decorators import is_admin 
from django.shortcuts import redirect, render, get_object_or_404

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

@login_required
@user_passes_test(is_admin)
def add_company_document(request):
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this company.")
    if request.method == 'POST':
        form = CompanyDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.tenant = request.user.tenant
            document.company_profile = get_object_or_404(CompanyProfile, tenant=request.tenant)
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
@user_passes_test(is_admin)
def delete_company_document(request, document_id):
    if hasattr(request, 'tenant') and request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this company.")
    
    try:
        # Get the user's StaffProfile (assuming one profile per user)
        company_profile = CompanyProfile.objects.get(tenant=request.tenant)
        document = get_object_or_404(CompanyDocument, id=document_id, company_profile=company_profile)
        if request.method == 'POST':
            document.delete()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)
        # raise BadRequest('Invalid request method')
    except StaffProfile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff profile not found'}, status=404)
    except StaffDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found or not owned by user'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

