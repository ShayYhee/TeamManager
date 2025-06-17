from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from documents.views import register, home, approve_document, send_approved_email, delete_document, view_my_profile, edit_my_profile, staff_directory, view_staff_profile, staff_list, notifications_view, dismiss_notification, add_staff_document, delete_staff_document, email_config, calendar_view
from documents.views import EventViewSet
from django.http import HttpResponse

router = DefaultRouter()
router.register('events', EventViewSet, basename='events')

def handle_well_known(request, path):
    return HttpResponse(status=204)  # Return 204 No Content

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", home, name="home"),
    path("documents/", include("documents.urls")),  # Added namespace
    path("accounts/", include("django.contrib.auth.urls")),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path("register/", register, name="register"),
    path("approve/<int:document_id>/", approve_document, name="approve_document"),
    path("send-email/<int:document_id>/", send_approved_email, name="send_approved_email"),
    path("delete/<int:document_id>/", delete_document, name="delete_document"),
    path("staff/", staff_directory, name="staff_directory"),
    path("staff/my-profile/", view_my_profile, name="view_my_profile"),
    path("staff/edit-profile/", edit_my_profile, name="edit_my_profile"),
    path("staff/<int:user_id>/", view_staff_profile, name="view_staff_profile"),
    path("staff/list", staff_list, name="staff_list"),
    path("staff/documents/add", add_staff_document, name="add_staff_document"),
    path("staff/documents/delete/<int:document_id>", delete_staff_document, name="delete_staff_document"),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/dismiss/', dismiss_notification, name='dismiss_notification'),
    path('email-config/', email_config, name='email_config'),
    path('api/', include(router.urls)),
    path('calendar/', calendar_view, name='calendar'),
    path('.well-known/<path:path>', handle_well_known),  # Handle .well-known requests
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)