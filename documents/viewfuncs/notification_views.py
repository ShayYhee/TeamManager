from datetime import timezone
import logging
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from documents.models import Notification, UserNotification

logger = logging.getLogger(__name__)

@login_required
def notifications_view(request):
    # Validate tenant access
    if not hasattr(request, 'tenant') or request.user.tenant != request.tenant:
        logger.error(f"Unauthorized access by user {request.user.username}: tenant mismatch")
        return HttpResponseForbidden("You are not authorized for this company.")

    # Fetch active UserNotifications for the current user (only those explicitly assigned)
    active_notifications = UserNotification.objects.filter(
        user=request.user,
        tenant=request.user.tenant,
        notification__is_active=True,
        dismissed=False
    ).select_related('notification').order_by('-notification__created_at')

    # Fetch dismissed UserNotifications for the current user
    dismissed_notifications = UserNotification.objects.filter(
        user=request.user,
        tenant=request.user.tenant,
        dismissed=True
    ).select_related('notification').order_by('-seen_at')

    return render(request, 'users/notifications.html', {
        'active_notifications': active_notifications,
        'dismissed_notifications': dismissed_notifications
    })

@require_POST
@login_required
def dismiss_notification(request):
    notification_id = request.POST.get('notification_id')
    try:
        notification = Notification.objects.get(id=notification_id, tenant=request.user.tenant)
        user_notification, created = UserNotification.objects.get_or_create(
            tenant=request.user.tenant,
            user=request.user,
            notification=notification,
            defaults={'seen_at': timezone.now()}
        )
        user_notification.dismissed = True
        user_notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

@require_POST
@login_required
def dismiss_all_notifications(request):
    try:
        # Update all non-dismissed UserNotifications for the user
        user_notifications = UserNotification.objects.filter(
            tenant=request.user.tenant,
            user=request.user,
            dismissed=False
        )
        updated_count = user_notifications.update(
            dismissed=True,
            seen_at=timezone.now()
        )
        return JsonResponse({'success': True, 'updated_count': updated_count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)