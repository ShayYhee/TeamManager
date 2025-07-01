import logging
from django.http import HttpResponseNotFound
from tenants.models import Tenant
from django.conf import settings

# Configure logging
logger = logging.getLogger(__name__)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        subdomain = host.split('.')[0]
        logger.debug(f"Host: {host}, Subdomain: {subdomain}")
        try:
            tenant = Tenant.objects.get(slug=subdomain)
            logger.debug(f"Found tenant: {tenant.slug}")
        except Tenant.DoesNotExist:
            logger.warning(f"No tenant found for subdomain: {subdomain}")
            if settings.DEBUG:
                try:
                    tenant = Tenant.objects.first()
                    logger.debug(f"Falling back to default tenant: {tenant.slug if tenant else 'None'}")
                    if not tenant:
                        logger.error("No tenants found in the database.")
                        return HttpResponseNotFound("No tenants found in the database.")
                except:
                    logger.error("Error accessing default tenant.")
                    return HttpResponseNotFound("No tenants found in the database.")
            else:
                logger.error(f"Tenant with subdomain '{subdomain}' not found in production.")
                return HttpResponseNotFound(f"Tenant with subdomain '{subdomain}' not found.")
        
        request.tenant = tenant
        logger.debug(f"Set request.tenant to: {tenant.slug}")
        return self.get_response(request)