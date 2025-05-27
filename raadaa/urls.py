"""
URL configuration for raadaa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from django.urls import path, include
from documents.views import register, home, approve_document, send_approved_email, delete_document, view_my_profile, edit_my_profile, staff_directory, view_staff_profile, staff_list, notifications_view, dismiss_notification
from django.shortcuts import redirect

def home_redirect(request):
    return redirect("document_list")  # Redirect "/" to the dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    # path("", home_redirect, name="home"),
    path("", home, name="home"),
    path("documents/", include("documents.urls")),
    path("accounts/", include("django.contrib.auth.urls")),  # Built-in auth views
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path("register/", register, name="register"),  # Custom signup
    path("approve/<int:document_id>/", approve_document, name="approve_document"),
    path("send-email/<int:document_id>/", send_approved_email, name="send_approved_email"),
    path("delete/<int:document_id>/", delete_document, name="delete_document"),
    path("staff/", staff_directory, name="staff_directory"),
    path("staff/my-profile/", view_my_profile, name="view_my_profile"),
    path("staff/edit-profile/", edit_my_profile, name="edit_my_profile"),
    path("staff/<int:user_id>/", view_staff_profile, name="view_staff_profile"),
    path("staff/list", staff_list, name="staff_list"),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/dismiss/', dismiss_notification, name='dismiss_notification'),
    # path("admin-access/", admin_access_page, name="admin-access"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
