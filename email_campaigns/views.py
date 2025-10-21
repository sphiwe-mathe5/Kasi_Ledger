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
from .email_utils import send_marketing_email
from .tasks import send_bulk_emails_task

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
    
    # Combine all unique emails
    all_customer_emails = list(set(list(style_ticket_emails) + list(booking_emails)))
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
            template = EmailTemplate.objects.get(id=template_id)
            
            # Apply AI modifications
            final_html = template.html_content
            if ai_prompt:
                final_html = apply_ai_editing(template.html_content, ai_prompt, user.company_name or "Our Business")
            
            # Handle images
            if images:
                final_html = handle_images_properly(final_html, images, request)
            
            # Queue emails for background processing
            send_bulk_emails_task.delay(
                user_id=user.id,
                customer_emails=all_customer_emails,
                subject=template.subject,
                html_content=final_html,
                images_data=[]  # Images already handled and in HTML
            )
            
            # Return immediately - emails sending in background
            messages.success(
                request, 
                f'✅ Emails are being sent to {customer_emails_count} customers in the background! '
                f'This may take a few minutes.'
            )
            
        except Exception as e:
            messages.error(request, f'Error queuing emails: {str(e)}')
    
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

    # Start the HTML section for images
    image_section = '''
    <div style="text-align: center; margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 10px;">
        <h3 style="color: #333; margin-bottom: 15px;">Special Offers</h3>
        <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 15px;">
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

            # Add image block to HTML
            image_section += f'''
            <div style="text-align: center;">
                <img src="{image_url}" alt="{uploaded_image.alt_text}"
                     style="max-width: 200px; height: auto; border-radius: 8px; margin-bottom: 10px; display: block;" />
                <p style="font-size: 12px; color: #666; margin: 0;">{uploaded_image.alt_text}</p>
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

    # Insert image section before footer if exists
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

logger = logging.getLogger(__name__)

def send_bulk_emails(user, customer_emails, subject, html_content, images):
    """Send marketing emails to all customers using Gmail"""
    sent_count = 0
    business_name = user.company_name or "Our Business"
    
    personalized_subject = f"{subject} - {business_name}"

    print(f"🔍 DEBUG: Preparing to send marketing emails via Gmail to {len(customer_emails)} recipients")
    logger.debug(f"Preparing to send emails to {len(customer_emails)} recipients")

    for email_address in customer_emails:
        try:
            print(f"📧 DEBUG: Sending marketing email to {email_address}")
            logger.debug(f"Sending email to {email_address}")

            # Personalize HTML
            personalized_html = html_content.replace('[Customer Name]', 'valued customer')
            personalized_html = personalized_html.replace('[CustomerEmail]', email_address)
            
            # Create plain text version
            plain_text = create_plain_text_version(personalized_html)
            
            # Send via Gmail backend
            send_marketing_email(
                to_email=email_address,
                subject=personalized_subject,
                html_content=personalized_html,
                plain_text=plain_text,
                business_name=business_name,
                reply_to=user.email
            )
            
            sent_count += 1
            print(f"✅ DEBUG: Successfully sent to {email_address} via Gmail")

            import time
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"❌ ERROR sending to {email_address}: {e}")
            traceback.print_exc()
            logger.error(f"Error sending to {email_address}: {e}")
            logger.debug(traceback.format_exc())

    print(f"📊 DEBUG: Finished sending. Successfully sent to {sent_count}/{len(customer_emails)} recipients.")
    logger.info(f"Finished sending emails: {sent_count}/{len(customer_emails)}")
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