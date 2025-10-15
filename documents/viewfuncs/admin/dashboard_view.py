from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render
from django.urls import reverse
from rba_decorators import is_admin, is_hr


@user_passes_test(is_admin)
def admin_dashboard(request):
    model_links = {
        "Departments": reverse("department_list"),
        "Events": reverse("event_list"),
        "Event Participants": reverse("event_participant_list"),
        "Notifications": reverse("admin_notification_list"),
        "Staff Profiles": reverse("staff_profile_list"),
        "Teams": reverse("admin_team_list"),
        "User Notifications": reverse("user_notification_list"),
        "Users": reverse("users_list"),
    }
    return render(request, "admin/admin_dashboard.html", {"model_links": model_links})

@login_required
@user_passes_test(is_hr)
def hr_dashboard(request):
    return render(request, 'hr/hr_dashboard.html')
