from django.urls import path
from .views import home, apply_for_tenant, application_status, create_tenant, tenant_list, reject_tenant, tenant_applications, check_status, edit_tenant, delete_tenant, verify_tenant, delete_tenant_app

urlpatterns = [
    path('', home, name='tenant_home'),
    path('apply-tenant/', apply_for_tenant, name='apply_for_tenant'),
    path('application-status/<int:identifier>/', application_status, name='application_status'),
    path('check-status/', check_status, name='check_status'),
    path('tenant-applications/', tenant_applications, name='tenant_applications'),
    path('tenant-applications/delte/<int:tenant_application_id>/', delete_tenant_app, name='delete_tenant_app'),
    path('create/<int:tenant_application_id>/', create_tenant, name='create_tenant'),
    path('reject/<int:tenant_application_id>/', reject_tenant, name='reject_tenant'),
    path('list/', tenant_list, name='tenant_list'),
    path('edit/<int:tenant_id>/', edit_tenant, name='edit_tenant'),
    path('delete/<int:tenant_id>/', delete_tenant, name='delete_tenant'),
    path('verify/<int:tenant_id>/', verify_tenant, name='verify_tenant'),
]