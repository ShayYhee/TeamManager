import logging
from django.http import HttpResponseNotFound, HttpResponseForbidden
from documents.models import CustomUser
from tenants.models import Tenant
from django.conf import settings

# Configure logging
logger = logging.getLogger(__name__)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Initialize tenant as None
        tenant = None

        # Early return for superusers to bypass tenant logic
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            request.tenant = None
            logger.debug("Superuser detected, bypassing tenant assignment")
            return self.get_response(request)

        # Extract subdomain from host
        host = request.get_host().split(':')[0]
        subdomain = host.split('.')[0]
        logger.debug(f"Host: {host}, Subdomain: {subdomain}")

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

        # Set tenant for authenticated non-superusers
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.tenant = tenant
            if not CustomUser.objects.filter(id=request.user.id, tenant=tenant).exists():
                logger.warning(f"User {request.user.username} not associated with tenant {tenant.slug}")
                return HttpResponseForbidden("You are not authorized to access this tenant.")
        else:
            request.tenant = tenant  # Set for unauthenticated users

        logger.debug(f"Set request.tenant to: {tenant.slug if tenant else 'None'}")
        return self.get_response(request)