from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import StyleTicket

@shared_task
def send_ticket_receipt_email(ticket_id):
    """Send receipt email asynchronously"""
    try:
        ticket = StyleTicket.objects.select_related('created_by', 'style', 'worker').get(id=ticket_id)
        
        subject = f"Your Style Ticket #{ticket.ticket_number}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [ticket.customer_email]

        html_content = render_to_string("saloon/email_receipt.html", {
            "ticket": ticket,
            "company_name": ticket.created_by.company_name or "Our",
        })
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        return f"Email sent successfully for ticket {ticket.ticket_number}"
    except StyleTicket.DoesNotExist:
        return f"Ticket {ticket_id} not found"
    except Exception as e:
        # Log the error but don't crash
        return f"Failed to send email: {str(e)}"