from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import logging

logger = logging.getLogger(__name__)


class GmailEmailBackend:
    """Custom Gmail backend for marketing emails"""
    
    def __init__(self):
        self.host = settings.GMAIL_HOST
        self.port = settings.GMAIL_PORT
        self.username = settings.GMAIL_HOST_USER
        self.password = settings.GMAIL_HOST_PASSWORD
        self.use_tls = settings.GMAIL_USE_TLS
        self.from_email = settings.GMAIL_FROM_EMAIL
    
    def send_email(self, to_email, subject, html_content, plain_text, from_name=None, reply_to=None):
        """Send email via Gmail SMTP"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{self.from_email}>" if from_name else self.from_email
            msg['To'] = to_email
            
            if reply_to:
                msg['Reply-To'] = reply_to
            
            # Add headers for bulk sending
            msg['X-Priority'] = '1'
            msg['X-MSMail-Priority'] = 'High'
            msg['Importance'] = 'high'
            msg['Precedence'] = 'bulk'
            if reply_to:
                msg['List-Unsubscribe'] = f'<mailto:{reply_to}?subject=Unsubscribe>'
            
            # Attach both plain text and HTML
            part1 = MIMEText(plain_text, 'plain')
            part2 = MIMEText(html_content, 'html')
            
            msg.attach(part1)
            msg.attach(part2)
            
            # Send via Gmail SMTP
            with smtplib.SMTP(self.host, self.port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Gmail send error to {to_email}: {e}")
            raise


def send_marketing_email(to_email, subject, html_content, plain_text, business_name, reply_to=None):
    """
    Send marketing emails using Gmail backend
    Use this for: bulk campaigns, newsletters, promotions
    """
    gmail = GmailEmailBackend()
    return gmail.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        plain_text=plain_text,
        from_name=business_name,
        reply_to=reply_to
    )