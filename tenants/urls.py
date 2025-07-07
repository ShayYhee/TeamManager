from django.urls import path
from .views import home, apply_for_tenant, application_status, create_tenant, tenant_list, reject_tenant, tenant_applications, check_status

urlpatterns = [
    path('home/', home, name='tenant_home'),
    path('apply-tenant/', apply_for_tenant, name='apply_for_tenant'),
    path('application-status/<str:username>/', application_status, name='application_status'),
    path('check-status/', check_status, name='check_status'),
    path('tenant-applications/', tenant_applications, name='tenant_applications'),
    path('create/<int:tenant_application_id>/', create_tenant, name='create_tenant'),
    path('reject/<int:tenant_application_id>/', reject_tenant, name='reject_tenant'),
    path('list/', tenant_list, name='tenant_list'),
]