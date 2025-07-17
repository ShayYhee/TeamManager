import logging
from django.http import HttpResponseNotFound, HttpResponseForbidden
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
            logger.debug("Superuser detected, bypassing tenant assignment")
            return self.get_response(request)

        # Extract host and determine if it's the main domain
        host = request.get_host().split(':')[0]  # Remove port if present
        domain_parts = host.split('.')
        main_domain = settings.MAIN_DOMAIN  # e.g., 'example.com' or 'localhost'

        # Check if the request is for the main domain (no subdomain)
        if host == main_domain or host == 'localhost':
            logger.debug("Request to main domain or localhost, no tenant required")
            request.tenant = None
            return self.get_response(request)

        # Extract subdomain (assumes format like tenant.example.com)
        if len(domain_parts) > 1:
            subdomain = domain_parts[0]
        else:
            logger.warning(f"Invalid host format: {host}")
            return HttpResponseNotFound("Invalid host format")

        # Try to find tenant by subdomain
        try:
            tenant = Tenant.objects.get(slug=subdomain)
            logger.debug(f"Found tenant: {tenant.slug}")
        except Tenant.DoesNotExist:
            logger.warning(f"No tenant found for subdomain: {subdomain}")
            if settings.DEBUG:
                tenant = Tenant.objects.first()
                if not tenant:
                    logger.error("No tenants found in the database.")
                    return HttpResponseNotFound("No tenants found in the database.")
                logger.debug(f"Falling back to default tenant: {tenant.slug}")
            else:
                logger.error(f"Tenant with subdomain '{subdomain}' not found in production.")
                return HttpResponseNotFound(f"Tenant with subdomain '{subdomain}' not found.")

        # Set tenant for the request
        request.tenant = tenant

        # Restrict access for authenticated non-superusers
        if hasattr(request, 'user') and request.user.is_authenticated:
            if not CustomUser.objects.filter(id=request.user.id, tenant=tenant).exists():
                logger.warning(f"User {request.user.username} not associated with tenant {tenant.slug}")
                return HttpResponseForbidden("You are not authorized to access this tenant.")

        logger.debug(f"Set request.tenant to: {tenant.slug if tenant else 'None'}")
        return self.get_response(request)