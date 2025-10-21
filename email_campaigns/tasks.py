from celery import shared_task
import time
import traceback
import logging
from .email_utils import send_marketing_email

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_marketing_email_task(self, to_email, subject, html_content, plain_text, business_name, reply_to):
    """
    Send a single marketing email asynchronously
    Retries up to 3 times with 60 second delays
    """
    try:
        logger.info(f"📧 Sending email to {to_email}")
        
        send_marketing_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            plain_text=plain_text,
            business_name=business_name,
            reply_to=reply_to
        )
        
        logger.info(f"✅ Successfully sent to {to_email}")
        time.sleep(0.5)  # Rate limiting
        return f"Sent to {to_email}"
        
    except Exception as e:
        logger.error(f"❌ Error sending to {to_email}: {e}")
        logger.debug(traceback.format_exc())
        
        # Retry the task
        raise self.retry(exc=e)

@shared_task
def send_bulk_emails_task(user_id, customer_emails, subject, html_content, images_data):
    """
    Queue individual email tasks for bulk sending
    Returns immediately while emails send in background
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        user = User.objects.get(id=user_id)
        business_name = user.company_name or "Our Business"
        personalized_subject = f"{subject} - {business_name}"
        
        logger.info(f"🔍 Queuing {len(customer_emails)} emails for background processing")
        
        # Queue each email as a separate task
        for email_address in customer_emails:
            # Personalize content
            personalized_html = html_content.replace('[Customer Name]', 'valued customer')
            personalized_html = personalized_html.replace('[CustomerEmail]', email_address)
            
            # Create plain text version
            plain_text = create_plain_text_version(personalized_html)
            
            # Queue the task
            send_marketing_email_task.delay(
                to_email=email_address,
                subject=personalized_subject,
                html_content=personalized_html,
                plain_text=plain_text,
                business_name=business_name,
                reply_to=user.email
            )
        
        logger.info(f"✅ Successfully queued {len(customer_emails)} email tasks")
        return len(customer_emails)
        
    except Exception as e:
        logger.error(f"❌ Error queuing bulk emails: {e}")
        logger.debug(traceback.format_exc())
        raise

def create_plain_text_version(html_content):
    """Create a plain text version for email clients"""
    import re
    text = re.sub(r'<[^<]+?>', '', html_content)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return text.strip()