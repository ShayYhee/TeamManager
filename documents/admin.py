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

class StaffDocumentInline(admin.TabularInline):
    model = StaffDocument
    extra = 1

class StaffProfileAdmin(admin.ModelAdmin):
    inlines = [StaffDocumentInline]

admin.site.register(Session, SessionAdmin)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role)
admin.site.register(Department)
admin.site.register(Team)
admin.site.register(StaffProfile, StaffProfileAdmin)
admin.site.register(Event)
admin.site.register(EventParticipant)
admin.site.register(UserNotification)
admin.site.register(CompanyProfile)
admin.site.register(Contact)
admin.site.register(Email)
admin.site.register(Folder, FolderAdmin)
admin.site.register(File)
admin.site.register(Attachment)
admin.site.register(Vacancy)
admin.site.register(VacancyApplication)
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'created_at', 'expires_at', 'is_active')
    list_filter = ('type', 'is_active')