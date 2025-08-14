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
        # Sync many-to-many team field
        if set(profile.team.all()) != set(instance.teams.all()):
            profile.team.set(instance.teams.all())
        if profile.phone_number != instance.phone_number:
            profile.phone_number = instance.phone_number
            profile.save(update_fields=['phone_number'])
    except StaffProfile.DoesNotExist:
        # If no StaffProfile exists, create one with the same department
        if instance.department:
            profile = StaffProfile.objects.create(
                user=instance,
                tenant=instance.tenant,
                department=instance.department,
                first_name=instance.first_name,
                last_name=instance.last_name,
                phone_number=instance.phone_number,
                email=instance.email
            )
            # Set many-to-many team field after creation
            profile.team.set(instance.teams.all())

@receiver(post_save, sender=StaffProfile)
def sync_profile_to_user_department(sender, instance, created, **kwargs):
    """
    When StaffProfile.department is updated, sync it to CustomUser.department.
    """
    user = instance.user
    if user.department != instance.department:
        user.department = instance.department
        user.save(update_fields=['department'])
    # Sync many-to-many teams field
    if set(user.teams.all()) != set(instance.team.all()):
        user.teams.set(instance.team.all())
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
