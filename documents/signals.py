from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings
from .models import StaffProfile, Role, CustomUser

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def sync_user_to_profile_department(sender, instance, created, **kwargs):
    """
    When CustomUser.department is updated, sync it to StaffProfile.department.
    """
    try:
        profile = instance.staff_profile
        if profile.department != instance.department:
            profile.department = instance.department
            profile.save(update_fields=['department'])
    except StaffProfile.DoesNotExist:
        # If no StaffProfile exists, create one with the same department
        if instance.department:
            StaffProfile.objects.create(
                user=instance,
                department=instance.department,
                first_name=instance.first_name,
                last_name=instance.last_name
            )

@receiver(post_save, sender=StaffProfile)
def sync_profile_to_user_department(sender, instance, created, **kwargs):
    """
    When StaffProfile.department is updated, sync it to CustomUser.department.
    """
    user = instance.user
    if user.department != instance.department:
        user.department = instance.department
        user.save(update_fields=['department'])

@receiver(m2m_changed, sender=CustomUser.roles.through)
def update_user_permissions(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        roles = Role.objects.filter(pk__in=pk_set)
        for role in roles:
            instance.user_permissions.add(*role.permissions.all())
    elif action == 'post_remove':
        roles = Role.objects.filter(pk__in=pk_set)
        for role in roles:
            instance.user_permissions.remove(*role.permissions.all())
    elif action == 'post_clear':
        instance.user_permissions.clear()

# @receiver(post_save, sender=settings.AUTH_USER_MODEL)
# def sync_user_to_profile_team(sender, instance, created, **kwargs):
#     """
#     When CustomUser.department is updated, sync it to StaffProfile.department.
#     """
#     try:
#         profile = instance.staff_profile
#         if profile.team != instance.team:
#             profile.team = instance.team
#             profile.save(update_fields=['team'])
#     except StaffProfile.DoesNotExist:
#         # If no StaffProfile exists, create one with the same department
#         if instance.team:
#             StaffProfile.objects.create(
#                 user=instance,
#                 team=instance.team,
#                 first_name=instance.first_name,
#                 last_name=instance.last_name
#             )

# @receiver(post_save, sender=StaffProfile)
# def sync_profile_to_user_team(sender, instance, created, **kwargs):
#     """
#     When StaffProfile.department is updated, sync it to CustomUser.department.
#     """
#     user = instance.user
#     if user.team != instance.team:
#         user.team = instance.team
#         user.save(update_fields=['team'])