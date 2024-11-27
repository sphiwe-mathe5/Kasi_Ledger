# email_sender/views.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import EmailForm
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def is_admin(user):
    if not user.is_staff:
        raise PermissionDenied("You don't have permission to access this page.")
    return True

@user_passes_test(is_admin)
@login_required
def send_email(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            recipient = form.cleaned_data['recipient']
            template = form.cleaned_data['template']
            
            # Render the HTML template from file
            html_message = render_to_string(f'emails/{template.filename}', {})
            
            send_mail(
                subject=template.subject,
                message='',  # Empty string for plain text version
                html_message=html_message,
                from_email='nazireemathe@gmail.com',
                recipient_list=[recipient],
                fail_silently=False,
            )
            
            messages.success(request, 'Email sent successfully!')
            return redirect('send_email')
    else:
        form = EmailForm()
    
    return render(request, 'emails/send_email.html', {'form': form})

