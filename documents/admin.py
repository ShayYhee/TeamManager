from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.sessions.models import Session
from .models import CustomUser, Role, Department, Team, StaffProfile, Notification, UserNotification, StaffDocument, Event, EventParticipant, CompanyProfile, Contact, Email, Folder, File, Attachment, Vacancy, VacancyApplication

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {
            "fields": ("tenant","roles", "phone_number","department","teams", "email_provider","email_address", "email_password")
        }),
    )
    filter_horizontal = ("roles",)  # Allows multi-select in admin
    list_display = ("tenant","username", "email", "phone_number", "is_staff", "is_active", "email_address")
    list_filter = ("tenant", "roles", "is_staff", "is_active")

class SessionAdmin(admin.ModelAdmin):
    def _session_data(self, obj):
        return obj.get_decoded()

    list_display = ['session_key', '_session_data', 'expire_date']
    list_filter = ['expire_date']
    readonly_fields = ['_session_data']
    exclude = ['session_data'] # Exclude the raw session_data field

class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'tenant', 'is_public', 'is_shared', 'created_by', 'share_time_end']
    list_filter = ['parent', 'is_public', 'is_shared', 'tenant']

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'hod']
    list_filter = ['tenant']

class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'department']
    list_filter = ['tenant']

class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'tenant', 'start_time', 'end_time']
    list_filter = ['tenant']

class ContactAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'name', 'email', 'phone', 'organization', 'designation', 'priority', 'is_public']
    list_filter = ['tenant', 'priority', 'is_public']

class EmailAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'subject', 'sender', 'to_emails', 'created_at']
    list_filter = ['tenant', 'created_at']

class VacancyAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'title', 'country', 'status', 'is_shared', 'created_by', 'created_at']
    list_filter = ['tenant', 'status', 'country', 'is_shared', 'created_at']

class VacancyApplicationAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'vacancy', 'first_name', 'last_name', 'phone', 'email', 'status', 'created_at']
    list_filter = ['tenant', 'status', 'created_at']
class StaffDocumentInline(admin.TabularInline):
    model = StaffDocument
    extra = 1

class StaffProfileAdmin(admin.ModelAdmin):
    inlines = [StaffDocumentInline]

admin.site.register(Session, SessionAdmin)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(StaffProfile, StaffProfileAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(EventParticipant)
admin.site.register(UserNotification)
admin.site.register(CompanyProfile)
admin.site.register(Contact, ContactAdmin)
admin.site.register(Email, EmailAdmin)
admin.site.register(Folder, FolderAdmin)
admin.site.register(File)
admin.site.register(Attachment)
admin.site.register(Vacancy, VacancyAdmin)
admin.site.register(VacancyApplication, VacancyApplicationAdmin)
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'created_at', 'expires_at', 'is_active')
    list_filter = ('type', 'is_active')