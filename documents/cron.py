from django_cron import CronJobBase, Schedule
from datetime import date, timedelta
from django.utils.timezone import now
from documents.models import StaffProfile, Notification

class BirthdayNotificationCronJob(CronJobBase):
    RUN_AT_TIMES = ['00:00']  # 12 AM daily

    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'yourapp.birthday_notification_cron'  # unique identifier

    def do(self):
        today = date.today()
        month = today.month
        day = today.day

        birthdays = StaffProfile.objects.filter(
            date_of_birth__month=month,
            date_of_birth__day=day
        )

        for staff in birthdays:
            title = f"It's {staff.full_name}'s Birthday Today! 🎉"
            if not Notification.objects.filter(title=title, type='birthday', created_at__date=today).exists():
                Notification.objects.create(
                    title=title,
                    type='birthday',
                    message='Wish them a happy birthday!',
                    is_active=True,
                    expires_at=now() + timedelta(hours=24)
                )
