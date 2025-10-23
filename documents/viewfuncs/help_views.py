# For Help and Support
from documents.forms import SupportForm
from documents.models import CustomUser
from django.http import JsonResponse
from django.shortcuts import render
from django.core.mail import EmailMessage
from .mail_connection import get_email_smtp_connection

def contact_support(request):
    if request.method == 'POST':
        print("POST data: %s", dict(request.POST))
        files = request.FILES.getlist('attachments')
        print("FILES data: %s", request.FILES)
        print(("FILES data: %s", [(f.name, f.size, f.content_type) for f in files] if files else "No files received"))
        form = SupportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = request.user
                superuser = CustomUser.objects.filter(is_active=True, is_superuser=True).first()
                if user.email_provider and user.email_address and user.email_password:
                    sender_provider = user.email_provider
                    sender_email = user.email_address
                    sender_password = user.email_password
                    from_email = user.email_address
                    cc = []
                else:
                    sender_provider = superuser.email_provider
                    sender_email = superuser.email_address
                    sender_password = superuser.get_smtp_password()
                    from_email = 'admin@teammanager.ng'
                    cc = [user.email_address]
                connection, error_message = get_email_smtp_connection(sender_provider, sender_email, sender_password)
                # Create email
                email = EmailMessage(
                    subject=form.cleaned_data['subject'],
                    body=form.cleaned_data['message'],
                    from_email=from_email,
                    to=['contact@teammanager.ng'],
                    cc=cc,
                    connection=connection
                )
                
                # Handle attachments
                for f in request.FILES.getlist('attachments'):
                    print(("Attaching file: %s (size: %s, type: %s)", f.name, f.size, f.content_type))
                    email.attach(f.name, f.read(), f.content_type)

                # for f in form.cleaned_data.get('attachments', []):
                #     print(("Attaching file: %s (size: %s, type: %s)", f.name, f.size, f.content_type))
                #     email.attach(f.name, f.read(), f.content_type)
                
                # Send email
                email.send()
                return JsonResponse({'success': True})
            except Exception as e:
                print(("Email sending error: %s", str(e)))
                return JsonResponse({'success': False, 'error': str(e)})
        else:
            print(("Form errors: %s", form.errors))
            return JsonResponse({'success': False, 'error': 'Invalid form data'})
    else:
        form = SupportForm()
    return render(request, 'dashboard/contact_support.html', {'form': form})
