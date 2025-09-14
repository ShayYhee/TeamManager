import logging
from django.http import HttpResponseNotFound, HttpResponseForbidden, HttpResponseServerError
from django.conf import settings
from django.urls import reverse
from urllib.parse import urlparse, urlunparse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
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
        main_domain = settings.MAIN_DOMAIN.split(':')[0]  # e.g., 'teammanager.ng'
        main_domain_parts = main_domain.split('.')  # e.g., ['teammanager', 'ng']
        domain_parts = host.split('.')  # e.g., ['teammanager', 'ng'] or ['sub', 'teammanager', 'ng']

        # NEW: Check if host matches main domain exactly or is localhost
        if host == main_domain or host == 'localhost':
            print("Request to main domain or localhost, no tenant required")
            request.tenant = None
            # Proceed to association check for authenticated users
        else:
            # Extract subdomain only if host has more parts than main domain
            if len(domain_parts) > len(main_domain_parts):
                subdomain = domain_parts[0]  # e.g., 'sub' from 'sub.teammanager.ng'
                print(f"Extracted subdomain: {subdomain}")
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
                print(f"User {request.user.username} not associated with tenant {request.tenant.slug if request.tenant else 'None'}")
                expected_subdomain = (
                    request.user.tenant.slug
                    if hasattr(request.user, 'tenant') and request.user.tenant
                    else None
                )
                if expected_subdomain is None:
                    logout(request)
                    raise PermissionDenied("You have no associated tenant. Contact support. faith.osebi@transnetcloud.com")
                print(f"Wrong user tenant slug: {expected_subdomain}")
                base_domain = "localhost:8000" if settings.DEBUG else "teammanager.ng"
                protocol = "http" if settings.DEBUG else "https"
                home_url = f"{protocol}://{expected_subdomain}.{base_domain}/"
                print(f"Redirecting to tenant home: {home_url}")
                return redirect(home_url)
        print(f"Set request.tenant to: {request.tenant.slug if request.tenant else 'None'}")
        return self.get_response(request)