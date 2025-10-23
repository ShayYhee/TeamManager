# For Help and Support
from documents.forms import SupportForm
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
                # Create email
                email = EmailMessage(
                    subject=form.cleaned_data['subject'],
                    body=form.cleaned_data['message'],
                    from_email=request.user.email_address if request.user.is_authenticated else 'no-reply@teammanager.ng',
                    to=['faith.osebi@transnetcloud.com'],
                    connection=get_email_smtp_connection(request.user.email_provider, request.user.email_address, request.user.email_password)
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
