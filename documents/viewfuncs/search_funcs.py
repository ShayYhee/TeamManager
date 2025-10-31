# for search bars...
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from documents.models import CustomUser, Contact

@login_required
def user_search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    # Build OR conditions across multiple fields
    users = CustomUser.objects.filter(
        tenant=request.user.tenant
    ).filter(
        Q(email__icontains=query) |
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).distinct()[:10]

    # Build full name safely
    results = [
        {   
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
        }
        for user in users
    ]

    return JsonResponse(results, safe=False)

@login_required
def contact_search(request):
    query = request.GET.get('q', '')
    contacts = Contact.objects.filter(
        tenant=request.user.tenant,  # Assuming tenant-based filtering
        email__icontains=query
    )[:10]  # Limit to 10 results
    results = [{'email': contact.email, 'name': contact.name} for contact in contacts]
    return JsonResponse(results, safe=False)