from django.contrib import admin
from django.shortcuts import render
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
from documents.views import view_user_details, admin_dashboard, admin_delete_document, admin_delete_file, admin_delete_folder, admin_document_details
from documents.views import admin_folder_list, admin_folder_details, admin_file_list, department_list, bulk_delete, create_user, bulk_action_users
from documents.views import delete_department, edit_department, create_department, admin_team_list, create_team, delete_team, edit_team
from documents.views import staff_profile_list, create_staff_profile, delete_staff_profile, edit_staff_profile, event_list, create_event, edit_event, delete_event
from documents.views import event_participant_list, create_event_participant, edit_event_participant, delete_event_participant
from documents.views import admin_notification_list, create_notification, edit_notification, delete_notification, edit_company_profile, view_company_profile
from documents.views import user_notification_list, create_user_notification, edit_user_notification, delete_user_notification
from documents.views import custom_404, custom_403, custom_500, custom_400, post_login_redirect, contact_list, create_contact, edit_contact, delete_contact, view_contact_detail
from documents.views import email_list, send_email, edit_email, delete_email, email_detail, save_draft
from documents.views import EventViewSet
from django.http import HttpResponse

router = DefaultRouter()
router.register('events', EventViewSet, basename='events')

def handle_well_known(request, path):
    return HttpResponse(status=204)  # Return 204 No Content

handler404 = custom_404
handler403 = custom_403
handler400 = custom_400
handler500 = custom_500

urlpatterns = [
    path('admin/', admin.site.urls),
    path('post-login/', post_login_redirect, name='post_login_redirect'),
    path("", home, name="home"),
    path("documents/", include("documents.urls")),  # Added namespace
    path("tenants/", include("tenants.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    # Override CKEditor upload
    path('ckeditor/upload/', custom_ckeditor_upload, name='ckeditor_upload'),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path("register/", register, name="register"),
    path("approve/<int:document_id>/", approve_document, name="approve_document"),
    path("send-email/<int:document_id>/", send_approved_email, name="send_approved_email"),
    path("delete/<int:document_id>/", delete_document, name="delete_document"),
    path("staff/", staff_directory, name="staff_directory"),
    path("staff/<int:user_id>/", view_staff_profile, name="view_staff_profile"),
    path("staff/list/", staff_list, name="staff_list"),
    path("staff/documents/add", add_staff_document, name="add_staff_document"),
    path("staff/documents/delete/<int:document_id>", delete_staff_document, name="delete_staff_document"),
    path('staff/export-csv/', export_staff_csv, name='export_staff_csv'),
    path('notifications/', notifications_view, name='notifications'),
    path('notifications/dismiss/', dismiss_notification, name='dismiss_notification'),
    path('notifications/dismiss-all/', dismiss_all_notifications, name='dismiss_all_notifications'),
    path('dashboard/email-config/', email_config, name='email_config'),
    path('api/', include(router.urls)),
    path('calendar/', calendar_view, name='calendar'),
    path("dashboard/my-profile/", view_my_profile, name="view_my_profile"),
    path("dashboard/my-profile/edit/", edit_my_profile, name="edit_my_profile"),
    path('dashboard/performance-dashboard/', performance_dashboard, name='performance_dashboard'),
    path('dashboard/hod-performance-dashboard/', hod_performance_dashboard, name='hod_performance_dashboard'),
    path('dashboard/contacts/', contact_list, name='contact_list'),
    path('dashboard/contacts/create/', create_contact, name='create_contact'),
    path('dashboard/contacts/<int:contact_id>/', view_contact_detail, name='view_contact_detail'),
    path('dashboard/contacts/edit/<int:contact_id>/', edit_contact, name='edit_contact'),
    path('dashboard/contacts/delete/<int:contact_id>/', delete_contact, name='delete_contact'),
    path('dashboard/emails/', email_list, name='email_list'),
    path('dashboard/emails/<int:email_id>', email_detail, name='email_detail'),
    path('dashboard/emails/save-draft/', save_draft, name='save_draft'),
    path('dashboard/emails/send/', send_email, name='send_email'),
    path('dashboard/emails/edit/<int:email_id>', edit_email, name='edit_email'),
    path('dashboard/emails/delete/<int:email_id>', delete_email, name='delete_email'),
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
    path('public-folders/', public_folder_list, name='public_folder_list'),
    path('public-folders/<int:public_folder_id>/', public_folder_list, name='public_folder_list'),
    path('public-folders/create/', create_public_folder, name='create_public_folder'),
    path('public-folders/<int:folder_id>/rename/', rename_public_folder, name='rename_public_folder'),
    path('public-folders/<int:folder_id>/move/', move_public_folder, name='move_public_folder'),
    path('public-folders/<int:folder_id>/delete/', delete_public_folder, name='delete_public_folder'),
    path('public-folders/files/upload/', upload_public_file, name='upload_public_file'),
    path('public-folders/files/<int:file_id>/rename/', rename_public_file, name='rename_public_file'),
    path('public-folders/files/<int:file_id>/move/', move_public_file, name='move_public_file'),
    path('public-folders/files/<int:file_id>/delete/', delete_public_file, name='delete_public_file'),
    path('tasks/', task_list, name='task_list'),
    path('tasks/create/', create_task, name='create_task'),
    path('tasks/<int:task_id>/update-status/', update_task_status, name='update_task_status'),
    path('tasks/<int:task_id>/', task_detail, name='task_detail'),
    path('tasks/<int:task_id>/reassign/', reassign_task, name='reassign_task'),
    path('tasks/<int:task_id>/delete/', delete_task, name='delete_task'),
    path('tasks/<int:task_id>/edit/', task_edit, name='task_edit'),
    path('tasks/<int:task_id>/delete-task-document/<int:doc_id>/', delete_task_document, name='delete_document'),
    path("admins/dashboard/", admin_dashboard, name="admin_dashboard"),
    path('admins/bulk-delete/<str:model_name>/', bulk_delete, name='bulk_delete'),
    # Users URLs
    path('admins/users/bulk-action/', bulk_action_users, name='bulk_action_users'),
    path('admins/users/list/', users_list, name='users_list'),
    path('admins/users/create/', create_user, name='create_user'),
    path('admins/users/view/<int:user_id>', view_user_details, name='view_user_details'),
    path('admins/users/approve/<int:user_id>', approve_user, name='approve_user'),
    path('admins/users/account-activation/', account_activation_sent, name='account_activation_sent'),
    path('admins/users/delete/<int:user_id>', delete_user, name='delete_user'),
    path('admins/users/edit/<int:user_id>', edit_user, name='edit_user'),
    # Department URLs
    path('admins/departments/', department_list, name='department_list'),
    path('admins/departments/create/', create_department, name='create_department'),
    path('admins/departments/edit/<int:department_id>/', edit_department, name='edit_department'),
    path('admins/departments/delete/<int:department_id>/', delete_department, name='delete_department'),
    # Team URLs
    path('admins/teams/', admin_team_list, name='admin_team_list'),
    path('admins/teams/create/', create_team, name='create_team'),
    path('admins/teams/edit/<int:team_id>/', edit_team, name='edit_team'),
    path('admins/teams/delete/<int:team_id>/', delete_team, name='delete_team'),
    # Staff Profile URLs
    path('admins/staff-profiles/', staff_profile_list, name='staff_profile_list'),
    path('admins/staff-profiles/create/', create_staff_profile, name='create_staff_profile'),
    path('admins/staff-profiles/edit/<int:staff_profile_id>/', edit_staff_profile, name='edit_staff_profile'),
    path('admins/staff-profiles/delete/<int:staff_profile_id>/', delete_staff_profile, name='delete_staff_profile'),
    # Events URLs
    path('admins/events/', event_list, name='event_list'),
    path('admins/events/create/', create_event, name='create_event'),
    path('admins/events/edit/<int:event_id>/', edit_event, name='edit_event'),
    path('admins/events/delete/<int:event_id>/', delete_event, name='delete_event'),
    # Event Participants URLs
    path('admins/event-participants/', event_participant_list, name='event_participant_list'),
    path('admins/event-participants/create/', create_event_participant, name='create_event_participant'),
    path('admins/event-participants/edit/<int:event_participant_id>/', edit_event_participant, name='edit_event_participant'),
    path('admins/event-participants/delete/<int:event_participant_id>/', delete_event_participant, name='delete_event_participant'),
    # Notifications URLs
    path('admins/notifications/list/', admin_notification_list, name='admin_notification_list'),
    path('admins/notifications/create/', create_notification, name='create_notification'),
    path('admins/notifications/edit/<int:notification_id>/', edit_notification, name='edit_notification'),
    path('admins/notifications/delete/<int:notification_id>/', delete_notification, name='delete_notification'),
    # User Notifications URLs
    path('admins/user-notifications/', user_notification_list, name='user_notification_list'),
    path('admins/user-notifications/create/', create_user_notification, name='create_user_notification'),
    path('admins/user-notifications/edit/<int:user_notification_id>/', edit_user_notification, name='edit_user_notification'),
    path('admins/user-notifications/delete/<int:user_notification_id>/', delete_user_notification, name='delete_user_notification'),
    # Company Profile URLs
    path('admins/company-profile/', edit_company_profile, name='edit_company_profile'),
    path('company-profile/', view_company_profile, name='view_company_profile'),

    path('.well-known/<path:path>', handle_well_known),  # Handle .well-known requests
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)