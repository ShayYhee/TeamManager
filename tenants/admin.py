from django.contrib import admin
from django.core.management import call_command
from .models import Tenant, TenantApplication
from documents.models import Role, CustomUser
import logging

logger = logging.getLogger(__name__)

# @admin.register(SuperUser)
# class SuperUserAdmin(admin.ModelAdmin):
#     list_display = ['username', 'email', 'password']

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at', 'created_by', 'admin']
    list_filter = ['created_at']
    search_fields = ['name', 'slug']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(customuser__id=request.user.id)
        return qs

@admin.register(TenantApplication)
class TenantApplicationAdmin(admin.ModelAdmin):
    list_display = ['organization_name', 'username', 'email', 'slug', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['organization_name', 'username', 'email', 'slug']
    actions = ['approve_application', 'reject_application']

    def approve_application(self, request, queryset):
        for application in queryset:
            if application.status != 'pending':
                self.message_user(request, f"Cannot approve non-pending application: {application.organization_name}")
                logger.warning(f"Cannot approve non-pending application: {application.organization_name}")
                continue
            try:
                tenant_admin = CustomUser.objects.get(username=application.username)
                tenant = Tenant.objects.create(
                    name=application.organization_name,
                    slug=application.slug,
                    created_by=request.user,
                    admin=tenant_admin
                )
                admin_role, _ = Role.objects.get_or_create(name='Admin')
                tenant_admin.tenant = tenant
                tenant_admin.roles.add(admin_role)
                tenant_admin.save()
                application.status = 'approved'
                application.save()
                logger.info(f"Approved tenant application: {application.organization_name} for user {application.username}")
            except Exception as e:
                logger.error(f"Error approving tenant application {application.organization_name}: {str(e)}")
                self.message_user(request, f"Error approving {application.organization_name}: {str(e)}", level='error')

    approve_application.short_description = "Approve selected tenant applications"

    def reject_application(self, request, queryset):
        for application in queryset:
            if application.status == 'pending':
                application.status = 'rejected'
                application.save()
                logger.info(f"Rejected tenant application: {application.organization_name}")
            else:
                logger.warning(f"Cannot reject non-pending application: {application.organization_name}")
                self.message_user(request, f"Cannot reject non-pending application: {application.organization_name}")

    reject_application.short_description = "Reject selected tenant applications"