import logging
from django.http import HttpResponseNotFound, HttpResponseForbidden, HttpResponseServerError
from django.conf import settings
from documents.models import CustomUser
from tenants.models import Tenant

# Configure logging
logger = logging.getLogger(__name__)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize tenant as None
        request.tenant = None

        # Early return for superusers to bypass tenant logic
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            print("Superuser detected, bypassing tenant assignment")
            return self.get_response(request)

        # Extract host and remove port if present
        host = request.get_host().split(':')[0]
        print(f"Raw host: {request.get_host()}, Processed host: {host}, REMOTE_ADDR: {request.META.get('REMOTE_ADDR')}")

        # Check if the request is for the main domain (no subdomain)
        main_domain = settings.MAIN_DOMAIN.split(':')[0]  # Remove port from MAIN_DOMAIN
        if host == main_domain or host == 'localhost':
            print("Request to main domain or localhost, no tenant required")
            request.tenant = None
            return self.get_response(request)

        # Extract subdomain (assumes format like tenant.teammanager.com)
        domain_parts = host.split('.')
        if len(domain_parts) > 1:
            subdomain = domain_parts[0]
            # Validate subdomain to ensure it's not  (prevent issues like ip addresses '13')
            if isinstance(subdomain, int):
                print(f"Invalid subdomain detected: {subdomain}")
                return HttpResponseNotFound("Invalid subdomain format")
        else:
            print(f"Invalid host format or no subdomain: {host}")
            return HttpResponseNotFound("Invalid host format or no subdomain")

        # Try to find tenant by subdomain
        try:
            tenant = Tenant.objects.get(slug=subdomain)
            print(f"Found tenant: {tenant.slug}")
            request.tenant = tenant
        except Tenant.DoesNotExist:
            print(f"Tenant with subdomain '{subdomain}' not found.")
            if settings.DEBUG:
                tenant = Tenant.objects.first()
                if tenant:
                    print(f"Falling back to default tenant: {tenant.slug}")
                    request.tenant = tenant
                else:
                    print("No tenants found in the database.")
                    return HttpResponseNotFound("No tenants found in the database.")
            else:
                return HttpResponseNotFound(f"Tenant with subdomain '{subdomain}' not found.")
        except Exception as e:
            print(f"Unexpected error in tenant lookup: {e}")
            return HttpResponseServerError("An unexpected server error occurred.")

        # Restrict access for authenticated non-superusers
        if hasattr(request, 'user') and request.user.is_authenticated:
            if not CustomUser.objects.filter(id=request.user.id, tenant=request.tenant).exists():
                print(f"User {request.user.username} not associated with tenant {request.tenant.slug}")
                return HttpResponseForbidden("You are not authorized to access this tenant.")

        print(f"Set request.tenant to: {request.tenant.slug if request.tenant else 'None'}")
        return self.get_response(request)