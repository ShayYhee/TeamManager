from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render
from ..rba_decorators import is_hr

@login_required
@user_passes_test(is_hr)
def hr_dashboard(request):
    return render(request, 'hr/hr_dashboard.html')
