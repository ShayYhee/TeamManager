from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role, Organization, Department, Team, StaffProfile

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {
            "fields": ("position", "roles", "phone_number", "smtp_email", "smtp_password")
        }),
    )
    filter_horizontal = ("roles",)  # Allows multi-select in admin
    list_display = ("username", "email", "phone_number", "position", "is_staff", "is_active", "smtp_email")
    list_filter = ("roles", "is_staff", "is_active")

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role)
admin.site.register(Organization)
admin.site.register(Department)
admin.site.register(Team)
admin.site.register(StaffProfile)