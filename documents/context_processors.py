from django.utils.timezone import now, timedelta
from .models import StaffProfile, Notification, UserNotification, CustomUser
import logging

logger = logging.getLogger(__name__)


def notification_count(request):
    # Validate tenant access
    # if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
    #     logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
    #     return {'unseen_notification_count': 0}
    print("Meer>>>>>", request)
        # Assuming this is in a view or similar context
    if request.user.is_authenticated:
        if request.user.is_superuser:
            # Superuser: Ignore tenant filter
            user = CustomUser.objects.get(username=request.user.username)
        else:
            # Regular user: Apply tenant filter
            user = CustomUser.objects.get(username=request.user.username, tenant=request.tenant)
        # active_notif = Notification.objects.filter(is_active=True)
        count = UserNotification.objects.filter(user=user, dismissed=False).count()
        return {'unseen_notification_count': count}
    return {'unseen_notification_count': 0}

def notification_bar(request):
    print("Yosh>>>>>", request)
    print("Yosh>>>>>", request.user)
    today = now().date()
    context = {
        'notification_bar_items': [],
        'birthday_self': False,
        'birthday_others': [],
    }

    # if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
    #     logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
    #     return context

    notifications = Notification.objects.filter(
        tenant=request.user.tenant if request.user.is_authenticated else None,
        is_active=True,
        type__in=[Notification.NotificationType.NEWS, Notification.NotificationType.ALERT, Notification.NotificationType.EVENT]
    ).order_by('-created_at')
    
    if request.user.is_authenticated:
        # Filter out dismissed notifications for the current user
        dismissed_ids = UserNotification.objects.filter(
            notification__tenant=request.user.tenant,
            user=request.user,
            dismissed=True
        ).values_list('notification_id', flat=True)
        notifications = notifications.exclude(id__in=dismissed_ids)
        context['notification_bar_items'] = [n for n in notifications if n.is_visible()]

        try:
            user_profile = StaffProfile.objects.get(user=request.user, tenant=request.user.tenant)
            user_birthday_today = (
                user_profile.date_of_birth and 
                user_profile.date_of_birth.month == today.month and 
                user_profile.date_of_birth.day == today.day
            )
        except StaffProfile.DoesNotExist:
            user_birthday_today = False

        # Get other staff with birthdays today (excluding current user)
        birthday_others_qs = StaffProfile.objects.filter(
            tenant=request.user.tenant,
            date_of_birth__month=today.month,
            date_of_birth__day=today.day
        ).exclude(user=request.user)

        if user_birthday_today:
            # Create or get birthday notification for self
            notification, created = Notification.objects.get_or_create(
                tenant=request.user.tenant,
                type=Notification.NotificationType.BIRTHDAY,
                title=f"Happy Birthday {user_profile.first_name}!",
                expire_at=now() + timedelta(days=1),
                defaults={
                    'message': f"Happy birthday, {user_profile.first_name}!!! Have a great year ahead! 🎉🎉🎉",
                    'created_at': now(),
                    'is_active': True,
                }
            )
            if notification.id not in dismissed_ids:
                context['notification_bar_items'].insert(0, notification)
            context['birthday_self'] = True

        if birthday_others_qs.exists():
            # Create or get birthday notification for others
            celebrant_names = ", ".join(
                f"{p.first_name} {p.last_name}" for p in birthday_others_qs
            )
            notification, created = Notification.objects.get_or_create(
                tenant=request.user.tenant,
                type=Notification.NotificationType.BIRTHDAY,
                title="Today's Birthdays",
                expire_at=now() + timedelta(days=1),
                defaults={
                    'message': f"It's {celebrant_names}'s birthday today! Wish them a happy birthday!",
                    'created_at': now(),
                    'is_active': True,
                }
            )
            if notification.id not in dismissed_ids:
                context['notification_bar_items'].insert(0, notification)
            context['birthday_others'] = list(birthday_others_qs)

    else:
        context['notification_bar_items'] = [n for n in notifications if n.is_visible()]

    return context

