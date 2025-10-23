from .viewfuncs.company_profile_views import view_company_profile
from .viewfuncs.contact_views import contact_list, create_contact, edit_contact, delete_contact, view_contact_detail, contact_search
from .viewfuncs.custom_auth import CustomLoginView, home, register, account_activation_sent, get_tenant_url, forgot_password, reset_password, password_reset_sent, password_reset_success, post_login_redirect
from .viewfuncs.custom_errors import custom_400, custom_403, custom_404, custom_500
from .viewfuncs.custom_settings import email_config, email_config_success_view
from .viewfuncs.document_views import document_list, delete_document
from .viewfuncs.editor_docs import custom_ckeditor_upload, create_from_editor
from .viewfuncs.email_views import email_list, save_draft, send_email, email_detail, delete_email, delete_email_attachment, edit_email
from .viewfuncs.events_views import EventViewSet, UserViewSet, EventParticipantResponseView, calendar_view
from .viewfuncs.file_views import upload_file, upload_file_anon, delete_file, move_file, rename_file, shared_file_view, enable_file_sharing
from .viewfuncs.folder_views import folder_view, create_folder, shared_folder_view, enable_folder_sharing, delete_folder, move_folder, rename_folder
from .viewfuncs.help_views import contact_support
from .viewfuncs.notification_views import notifications_view, dismiss_notification, dismiss_all_notifications
from .viewfuncs.performance_dashboard import performance_dashboard, hod_performance_dashboard
from .viewfuncs.profile_views import view_my_profile, edit_my_profile
from .viewfuncs.staff_views import staff_directory, view_staff_profile, staff_list, add_staff_document, delete_staff_document, staff_list, export_staff_csv
from .viewfuncs.task_views import task_list, task_detail, create_task, update_task_status, reassign_task, delete_task, task_edit, delete_task_document
from .viewfuncs.template_docs import create_document, approve_document, autocomplete_sales_rep, send_approved_email
from .viewfuncs.admin.bulk_actions import bulk_delete, bulk_action_users
from .viewfuncs.admin.company_profile_views import edit_company_profile, add_company_document, delete_company_document
from .viewfuncs.admin.dashboard_views import admin_dashboard
from .viewfuncs.admin.department_views import assign_users_to_department, department_list, create_department, edit_department, delete_department
from .viewfuncs.admin.document_views import admin_documents_list, admin_document_details, admin_delete_document
from .viewfuncs.admin.event_views import create_event, event_list, delete_event, create_event_participant, event_participant_list, delete_event_participant, edit_event, edit_event_participant
from .viewfuncs.admin.file_views import admin_file_list, admin_delete_file
from .viewfuncs.admin.folder_views import admin_folder_list, admin_delete_folder, admin_folder_details
from .viewfuncs.admin.notifications_views import admin_notification_list, create_notification, edit_notification, delete_notification
from .viewfuncs.admin.staff_profile_views import staff_profile_list, create_staff_profile, edit_staff_profile, delete_staff_profile
from .viewfuncs.admin.task_views import admin_task_list, admin_task_detail
from .viewfuncs.admin.team_views import assign_teams_to_users, admin_team_list, create_team, edit_team, delete_team
from .viewfuncs.admin.user_notifications_views import user_notification_list, create_user_notification, edit_user_notification, delete_user_notification
from .viewfuncs.admin.user_views import create_user, users_list, view_user_details, approve_user, edit_user, delete_user
from .viewfuncs.hr.dashboard_views import hr_dashboard
from .viewfuncs.hr.vacancy_application_views import vacancy_application_list, send_vacancy_application_received, create_vacancy_application
from .viewfuncs.hr.vacancy_application_views import applications_per_vacancy, vacancy_application_detail, delete_vacancy_application, send_vacancy_accepted_mail, send_vacancy_rejected_mail, accept_vac_app, reject_vac_app, fetch_accepted_applications, fetch_rejected_applications
from .viewfuncs.hr.vacancy_views import vacancy_list, create_vacancy, edit_vacancy, vacancy_detail, delete_vacancy, share_vacancy, withdraw_vacancy, vacancy_post