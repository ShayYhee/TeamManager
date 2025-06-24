from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from documents.views import register, home, approve_document, send_approved_email, delete_document, view_my_profile
from documents.views import edit_my_profile, staff_directory, view_staff_profile, staff_list, notifications_view
from documents.views import dismiss_notification, add_staff_document, delete_staff_document, email_config, calendar_view
from documents.views import users_list, approve_user, account_activation_sent, delete_user, edit_user, custom_ckeditor_upload
from documents.views import dismiss_all_notifications, export_staff_csv, performance_dashboard, hod_performance_dashboard, folder_list
from documents.views import create_folder, upload_file, update_task_status, create_task, task_list, task_detail, reassign_task, delete_task
from documents.views import delete_folder, delete_file, rename_folder, rename_file, move_folder, move_file, task_edit, delete_task_document
from documents.views import performance_dashboard, hod_performance_dashboard, create_public_folder, delete_public_folder, rename_public_folder
from documents.views import public_folder_list, move_public_folder, upload_public_file, delete_public_file, rename_public_file, move_public_file
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
    # Override CKEditor upload
    path('ckeditor/upload/', custom_ckeditor_upload, name='ckeditor_upload'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path("register/", register, name="register"),
    path("approve/<int:document_id>/", approve_document, name="approve_document"),
    path("send-email/<int:document_id>/", send_approved_email, name="send_approved_email"),
    path("delete/<int:document_id>/", delete_document, name="delete_document"),
    path("staff/", staff_directory, name="staff_directory"),
    path("users/my-profile/", view_my_profile, name="view_my_profile"),
    path("users/edit-profile/", edit_my_profile, name="edit_my_profile"),
    path("staff/<int:user_id>/", view_staff_profile, name="view_staff_profile"),
    path("staff/list", staff_list, name="staff_list"),
    path("staff/documents/add", add_staff_document, name="add_staff_document"),
    path("staff/documents/delete/<int:document_id>", delete_staff_document, name="delete_staff_document"),
    path('staff/export-csv/', export_staff_csv, name='export_staff_csv'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/dismiss/', dismiss_notification, name='dismiss_notification'),
    path('notifications/dismiss-all/', dismiss_all_notifications, name='dismiss_all_notifications'),
    path('users/email-config/', email_config, name='email_config'),
    path('api/', include(router.urls)),
    path('calendar/', calendar_view, name='calendar'),
    path('users/list/', users_list, name='users_list'),
    path('users/approve/<int:user_id>', approve_user, name='approve_user'),
    path('users/account-activation/', account_activation_sent, name='account_activation_sent'),
    path('users/delete/<int:user_id>', delete_user, name='delete_user'),
    path('users/edit/<int:user_id>', edit_user, name='edit_user'),
    path('dashboard/performance-dashboard/', performance_dashboard, name='performance_dashboard'),
    path('dashboard/hod-performance-dashboard/', hod_performance_dashboard, name='hod_performance_dashboard'),
    path('folders/', folder_list, name='folder_list'),
    path('folders/<int:parent_id>/', folder_list, name='folder_list'),
    path('folders/create/', create_folder, name='create_folder'),
    path('folders/upload/', upload_file, name='upload_file'),
    path('folders/<int:folder_id>/delete/', delete_folder, name='delete_folder'),
    path('folders/files/<int:file_id>/delete/', delete_file, name='delete_file'),
    path('folders/<int:folder_id>/rename/', rename_folder, name='rename_folder'),
    path('folders/files/<int:file_id>/rename/', rename_file, name='rename_file'),
    path('folders/<int:folder_id>/move/', move_folder, name='move_folder'),
    path('folders/files/<int:file_id>/move/', move_file, name='move_file'),
    path('public_folders/', public_folder_list, name='public_folder_list'),
    path('public_folders/<int:public_folder_id>/', public_folder_list, name='public_folder_list'),
    path('public_folders/create/', create_public_folder, name='create_public_folder'),
    path('public_folders/<int:folder_id>/rename/', rename_public_folder, name='rename_public_folder'),
    path('public_folders/<int:folder_id>/move/', move_public_folder, name='move_public_folder'),
    path('public_folders/<int:folder_id>/delete/', delete_public_folder, name='delete_public_folder'),
    path('public_folders/files/upload/', upload_public_file, name='upload_public_file'),
    path('public_folders/files/<int:file_id>/rename/', rename_public_file, name='rename_public_file'),
    path('public_folders/files/<int:file_id>/move/', move_public_file, name='move_public_file'),
    path('public_folders/files/<int:file_id>/delete/', delete_public_file, name='delete_public_file'),
    path('tasks/', task_list, name='task_list'),
    path('tasks/create/', create_task, name='create_task'),
    path('tasks/<int:task_id>/update-status/', update_task_status, name='update_task_status'),
    path('tasks/<int:task_id>/', task_detail, name='task_detail'),
    path('tasks/<int:task_id>/reassign/', reassign_task, name='reassign_task'),
    path('tasks/<int:task_id>/delete/', delete_task, name='delete_task'),
    path('tasks/<int:task_id>/edit/', task_edit, name='task_edit'),
    path('tasks/<int:task_id>/delete-task-document/<int:doc_id>/', delete_task_document, name='delete_document'),
    path('.well-known/<path:path>', handle_well_known),  # Handle .well-known requests
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)