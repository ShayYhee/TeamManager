from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role, Organization, Department, Team, StaffProfile, Notification, UserNotification, StaffDocument, Event, EventParticipant

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {
            "fields": ("roles", "phone_number","department","teams", "smtp_email", "smtp_password")
        }),
    )
    filter_horizontal = ("roles",)  # Allows multi-select in admin
    list_display = ("username", "email", "phone_number", "is_staff", "is_active", "smtp_email")
    list_filter = ("roles", "is_staff", "is_active")

class StaffDocumentInline(admin.TabularInline):
    model = StaffDocument
    extra = 1

class StaffProfileAdmin(admin.ModelAdmin):
    inlines = [StaffDocumentInline]

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role)
admin.site.register(Organization)
admin.site.register(Department)
admin.site.register(Team)
# admin.site.unregister(StaffProfile)
admin.site.register(StaffProfile, StaffProfileAdmin)
admin.site.register(Event)
admin.site.register(EventParticipant)
admin.site.register(UserNotification)
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'created_at', 'expires_at', 'is_active')
    list_filter = ('type', 'is_active')