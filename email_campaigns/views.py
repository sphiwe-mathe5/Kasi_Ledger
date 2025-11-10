from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
import openai
import uuid
import os
from uuid import uuid4
from saloon.models import StyleTicket, Booking
from .models import EmailTemplate
from .models import CampaignImage
from django.utils.html import escape
from saloon.subscriptions import check_feature_access
from core.models import Product
from carwash.models import ServiceTicket

@login_required
def emails(request):
    """Simple email marketing - one page, one action"""
    user = request.user
    
    # Check subscription access for email marketing
    access = check_feature_access(user, 'email_marketing')
    
    # Get all unique customer emails from StyleTicket for this user
    style_ticket_emails = StyleTicket.objects.filter(
        created_by=user,
        customer_email__isnull=False
    ).exclude(customer_email='').values_list('customer_email', flat=True).distinct()
    
    # Get all unique customer emails from Booking for this user (if applicable)
    booking_emails = []
    try:
        booking_emails = Booking.objects.filter(
            salon__user=user,
            customer_email__isnull=False
        ).exclude(customer_email='').values_list('customer_email', flat=True).distinct()
    except:
        pass
    
    # Get all unique customer emails from Product sales
    product_emails = Product.objects.filter(
        user=user,
        customer_email__isnull=False
    ).exclude(customer_email='').values_list('customer_email', flat=True).distinct()
    
    # ✅ NEW: Get all unique customer emails from ServiceTicket (Car Wash)
    service_ticket_emails = ServiceTicket.objects.filter(
        created_by=user,
        customer_email__isnull=False
    ).exclude(customer_email='').values_list('customer_email', flat=True).distinct()
    
    # Combine all unique emails
    all_customer_emails = list(set(
        list(style_ticket_emails) + 
        list(booking_emails) + 
        list(product_emails) +
        list(service_ticket_emails)  # ✅ NEW: Include car wash emails
    ))
    customer_emails_count = len(all_customer_emails)
    
    # Get available templates
    templates = EmailTemplate.objects.filter(is_active=True, is_system_template=True)
    
    # Handle form submission - ONLY if user has access
    if request.method == 'POST':
        # Re-check access on POST to prevent bypassing
        if not access['allowed']:
            messages.error(request, access['message'])
            return redirect('email_campaigns:emails')
        
        # Get form data
        template_id = request.POST.get('template')
        ai_prompt = request.POST.get('ai_prompt')
        images = request.FILES.getlist('images')
        
        if not template_id:
            messages.error(request, 'Please select a template.')
            return redirect('email_campaigns:emails')
        
        if customer_emails_count == 0:
            messages.error(request, 'No customer emails found. You need to have customers with email addresses in your system.')
            return redirect('email_campaigns:emails')
        
        try:
            # Get the selected template
            template = EmailTemplate.objects.get(id=template_id)
            
            # Apply AI modifications if prompt provided
            final_html = template.html_content
            if ai_prompt:
                final_html = apply_ai_editing(template.html_content, ai_prompt, user.company_name or "Our Business")
            
            # Handle image uploads properly
            if images:
                final_html = handle_images_properly(final_html, images, request)
            
            # Send emails to all customers
            sent_count = send_bulk_emails(user, all_customer_emails, template.subject, final_html, images)
            
            messages.success(request, f'✅ Email sent successfully to {sent_count} customers!')
            
        except Exception as e:
            messages.error(request, f'Error sending emails: {str(e)}')
    
    context = {
        'customer_emails_count': customer_emails_count,
        'customer_emails': all_customer_emails,
        'templates': templates,
        'has_email_access': access['allowed'],
        'access_message': access['message'],
    }
    return render(request, 'email_campaigns/simple_marketing.html', context)

def apply_ai_editing(original_html, prompt, business_name):
    """Use AI to modify the email content safely and naturally"""
    try:
        openai.api_key = settings.OPENAI_API_KEY

        ai_prompt = f"""
        You are a helpful business assistant that writes professional, human-sounding email content.

        TASK:
        Modify the following HTML email template based on the user's request.

        Original HTML:
        {original_html}

        User's Request:
        {prompt}

        Business Name: {business_name}

        RULES:
        - Keep the EXACT same HTML structure and CSS styles.
        - Only change the text content; do not remove or reorder sections.
        - Use a warm, personal tone — sound like a real person, not a marketer.
        - Write naturally and conversationally, like a trusted local business owner.
        - Avoid anything that could trigger spam filters:
          * No excessive punctuation (!!!, ???)
          * No ALL CAPS
          * No words like "FREE", "LIMITED TIME", "BUY NOW", "ACT FAST", etc.
          * No clickbait or aggressive sales phrases
        - Keep it short, respectful, and value-focused.
        - Replace [Your Business Name] with the actual business name: {business_name}.
        - Do NOT include any explanations or comments — output ONLY the modified HTML.
        - NEVER wrap the HTML in markdown code blocks like ```html or ```. Return ONLY raw HTML.
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional email copywriter specializing in high-deliverability, "
                        "authentic business communication. "
                        "Your goal is to make the text personal, natural, and friendly — never spammy. "
                        "CRITICAL: Return ONLY raw HTML without any markdown formatting or code blocks."
                    ),
                },
                {"role": "user", "content": ai_prompt}
            ],
            max_tokens=1500,
            temperature=0.6,
        )

        modified_html = response.choices[0].message["content"].strip()
        
        # Remove markdown code blocks if AI adds them anyway
        modified_html = modified_html.replace('```html', '').replace('```', '').strip()
        
        return modified_html

    except Exception as e:
        print(f"AI Editing Error: {e}")
        return original_html


def wrap_email_with_professional_styling(html_content, business_name, user):
    """
    Wrap the email content in a beautiful, responsive email template
    """
    
    # Extract just the body content if it's a full HTML document
    if '<body' in html_content.lower():
        import re
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            html_content = body_match.group(1)
    
    # Get business category for color scheme
    category_colors = {
        'salon': {'primary': '#E91E63', 'secondary': '#F06292', 'accent': '#FCE4EC'},
        'car_wash': {'primary': '#2196F3', 'secondary': '#64B5F6', 'accent': '#E3F2FD'},
        'restaurant': {'primary': '#FF5722', 'secondary': '#FF8A65', 'accent': '#FBE9E7'},
        'clothing_brand': {'primary': '#9C27B0', 'secondary': '#BA68C8', 'accent': '#F3E5F5'},
        'spaza': {'primary': '#4CAF50', 'secondary': '#81C784', 'accent': '#E8F5E9'},
    }
    
    colors = category_colors.get(user.company_category, {
        'primary': '#667eea',
        'secondary': '#764ba2',
        'accent': '#f8f9fa'
    })
    
    styled_email = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{business_name}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
    
    <!-- Wrapper Table -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f4f4;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                
                <!-- Main Container -->
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" 
                       style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); overflow: hidden; max-width: 100%;">
                    
                    <!-- Header with Gradient -->
                    <tr>
                        <td style="background: linear-gradient(135deg, {colors['primary']} 0%, {colors['secondary']} 100%); 
                                   padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700; 
                                       letter-spacing: -0.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                {business_name}
                            </h1>
                            <p style="margin: 10px 0 0 0; color: rgba(255,255,255,0.95); font-size: 14px; 
                                      font-weight: 400; letter-spacing: 0.5px;">
                                Bringing you something special
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Main Content Area -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <!-- Dynamic Content Goes Here -->
                            {html_content}
                        </td>
                    </tr>
                    
                    <!-- Divider -->
                    <tr>
                        <td style="padding: 0 30px;">
                            <div style="height: 1px; background: linear-gradient(to right, transparent, {colors['primary']}, transparent);"></div>
                        </td>
                    </tr>
                    
                    <!-- Call to Action Section -->
                    <tr>
                        <td style="padding: 30px; text-align: center; background-color: {colors['accent']};">
                            <p style="margin: 0 0 20px 0; color: #333; font-size: 16px; font-weight: 500;">
                                Ready to experience more?
                            </p>
                            <a href="tel:{user.phone_number if user.phone_number else ''}" 
                               style="display: inline-block; background: linear-gradient(135deg, {colors['primary']}, {colors['secondary']}); 
                                      color: #ffffff; text-decoration: none; padding: 14px 40px; border-radius: 25px; 
                                      font-weight: 600; font-size: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.15);
                                      transition: transform 0.2s;">
                                📞 Contact Us
                            </a>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px; text-align: center; background-color: #2c3e50; color: #ffffff;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td style="padding-bottom: 15px;">
                                        <h3 style="margin: 0 0 10px 0; font-size: 18px; font-weight: 600; color: #ffffff;">
                                            {business_name}
                                        </h3>
                                        {f'<p style="margin: 0; font-size: 14px; color: rgba(255,255,255,0.8);">📞 {user.phone_number}</p>' if user.phone_number else ''}
                                        <p style="margin: 5px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.8);">
                                            📧 {user.email}
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.2);">
                                        <p style="margin: 0; font-size: 12px; color: rgba(255,255,255,0.6); line-height: 1.6;">
                                            You're receiving this email because you're a valued customer of {business_name}.
                                        </p>
                                        <p style="margin: 10px 0 0 0; font-size: 11px; color: rgba(255,255,255,0.5);">
                                            <a href="mailto:{user.email}?subject=Unsubscribe" 
                                               style="color: rgba(255,255,255,0.7); text-decoration: underline;">
                                                Unsubscribe
                                            </a> | 
                                            © {business_name} {import_datetime().year}
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
    
</body>
</html>
    '''
    
    return styled_email


def import_datetime():
    """Helper to get current year"""
    from datetime import datetime
    return datetime


def handle_images_properly(html_content, images, request):
    """
    Upload images to Google Cloud Storage via CampaignImage model,
    inject public URLs into the email HTML, and provide debug logs.
    """
    if not images:
        print("🟡 DEBUG: No images uploaded.")
        return html_content

    user = request.user
    print(f"🟢 DEBUG: Handling {len(images)} uploaded images for user {user.username}")

    # Start the HTML section for images with beautiful styling
    image_section = '''
    <div style="margin: 30px 0; padding: 0;">
        <h2 style="color: #333; margin: 0 0 20px 0; font-size: 22px; font-weight: 600; text-align: center;">
            ✨ Special Offers ✨
        </h2>
        <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 25px;">
    '''

    for image_file in images:
        try:
            print(f"📤 DEBUG: Uploading image '{image_file.name}'")
            
            # Save image using the model - Django will handle the unique naming
            uploaded_image = CampaignImage.objects.create(
                campaign=None,
                image=image_file,
                alt_text=os.path.splitext(image_file.name)[0]
            )

            # Get the public URL
            image_url = uploaded_image.image.url
            print(f"🔗 DEBUG: Image saved to: {uploaded_image.image.name}")
            print(f"🔗 DEBUG: Public URL: {image_url}")

            # Add image block to HTML with modern card styling
            image_section += f'''
            <div style="background: #ffffff; border-radius: 12px; overflow: hidden; 
                        box-shadow: 0 2px 12px rgba(0,0,0,0.08); transition: transform 0.2s;
                        max-width: 280px; margin: 0 auto;">
                <img src="{image_url}" alt="{uploaded_image.alt_text}"
                     style="width: 100%; height: 200px; object-fit: cover; display: block; border: none;" />
            </div>
            '''

        except Exception as e:
            print(f"❌ ERROR: Failed to process image '{image_file.name}': {e}")
            import traceback
            traceback.print_exc()

    image_section += '''
        </div>
    </div>
    '''

    # Insert image section
    if '<div class="footer">' in html_content:
        final_html = html_content.replace('<div class="footer">', image_section + '<div class="footer">')
    elif '</body>' in html_content:
        final_html = html_content.replace('</body>', image_section + '</body>')
    else:
        final_html = html_content + image_section

    print("✅ DEBUG: Image section successfully injected into HTML.")
    return final_html


import traceback
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def send_bulk_emails(user, customer_emails, subject, html_content, images):
    """Send beautifully styled marketing emails to all customers using Gmail"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    sent_count = 0
    business_name = user.company_name or user.username or "Our Business"
    personalized_subject = f"{subject} - {business_name}"

    print(f"🔍 DEBUG: Preparing to send emails via Gmail to {len(customer_emails)} recipients")
    logger.debug(f"Preparing to send emails to {len(customer_emails)} recipients")

    # Create Gmail SMTP connection
    try:
        print(f"🔌 Connecting to Gmail SMTP: {settings.GMAIL_HOST}:{settings.GMAIL_PORT}")
        server = smtplib.SMTP(settings.GMAIL_HOST, int(settings.GMAIL_PORT), timeout=30)
        server.starttls()
        server.login(settings.GMAIL_HOST_USER, settings.GMAIL_HOST_PASSWORD)
        print(f"✅ Gmail SMTP connection established")
    except Exception as e:
        print(f"❌ Failed to connect to Gmail: {e}")
        logger.error(f"Gmail connection failed: {e}")
        return 0

    for email_address in customer_emails:
        try:
            print(f"📧 DEBUG: Sending email to {email_address}")

            # Personalize HTML content
            personalized_html = html_content.replace('[Customer Name]', 'valued customer')
            personalized_html = personalized_html.replace('[CustomerEmail]', email_address)
            personalized_html = personalized_html.replace('[Your Business Name]', business_name)
            
            # Wrap content in professional email template
            final_html = wrap_email_with_professional_styling(personalized_html, business_name, user)
            plain_text = create_plain_text_version(personalized_html)

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = personalized_subject
            msg['From'] = f"{business_name} <{settings.GMAIL_FROM_EMAIL}>"
            msg['To'] = email_address
            msg['Reply-To'] = user.email
            
            # Add headers
            msg['X-Priority'] = '3'
            msg['Precedence'] = 'bulk'
            msg['List-Unsubscribe'] = f'<mailto:{user.email}?subject=Unsubscribe>'
            
            # Attach plain text and HTML
            part1 = MIMEText(plain_text, 'plain', 'utf-8')
            part2 = MIMEText(final_html, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send
            server.send_message(msg)
            
            sent_count += 1
            print(f"✅ DEBUG: Successfully sent to {email_address}")

            import time
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"❌ ERROR sending to {email_address}: {e}")
            traceback.print_exc()
            logger.error(f"Error sending to {email_address}: {e}")

    # Close connection
    try:
        server.quit()
        print(f"🔌 Gmail SMTP connection closed")
    except:
        pass

    print(f"📊 DEBUG: Finished sending. Successfully sent to {sent_count}/{len(customer_emails)} recipients.")
    logger.info(f"Finished sending emails via Gmail: {sent_count}/{len(customer_emails)}")
    return sent_count


def create_plain_text_version(html_content):
    """Create a plain text version for email clients that prefer it"""
    import re
    # Remove HTML tags
    text = re.sub(r'<[^<]+?>', '', html_content)
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Replace common HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    return text.strip()