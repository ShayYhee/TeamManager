from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("role", "phone_number", "smtp_email", "smtp_password")}),
    )
    list_display = ("username", "email", "phone_number", "role", "is_staff", "is_active", "smtp_email")
    list_filter = ("role", "is_staff", "is_active")

admin.site.register(CustomUser, CustomUserAdmin)