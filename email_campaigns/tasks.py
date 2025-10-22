from background_task import background
import time
import traceback
import logging
from .email_utils import send_marketing_email

logger = logging.getLogger(__name__)

@background(schedule=0)  # Run immediately
def send_single_email_task(to_email, subject, html_content, plain_text, business_name, reply_to):
    """Send a single email in the background"""
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
        
    except Exception as e:
        logger.error(f"❌ Error sending to {to_email}: {e}")
        logger.debug(traceback.format_exc())

def create_plain_text_version(html_content):
    """Create a plain text version for email clients"""
    import re
    text = re.sub(r'<[^<]+?>', '', html_content)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return text.strip()