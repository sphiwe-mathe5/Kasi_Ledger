from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from core.project.gcloud import GoogleCloudMediaFileStorage

class CustomerEmail(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_emails')
    email = models.EmailField()
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_contacted = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        unique_together = ['user', 'email']
        verbose_name_plural = "Customer Emails"
    
    def __str__(self):
        return f"{self.email} ({self.user.username})"

class EmailTemplate(models.Model):
    TEMPLATE_CATEGORIES = [
        ('promotional', 'Promotional'),
        ('newsletter', 'Newsletter'),
        ('holiday', 'Holiday'),
        ('announcement', 'Announcement'),
        ('welcome', 'Welcome'),
        ('followup', 'Follow-up'),
    ]
    
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=TEMPLATE_CATEGORIES, default='promotional')
    subject = models.CharField(max_length=200)
    html_content = models.TextField()
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_system_template = models.BooleanField(default=False)  # For pre-built templates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Email Templates"
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

class EmailCampaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled')
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_campaigns')
    name = models.CharField(max_length=100)
    template = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE)
    recipient_emails = models.ManyToManyField(CustomerEmail, through='CampaignRecipient')
    scheduled_for = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Email Campaigns"
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"

class CampaignRecipient(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ]
    
    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE)
    customer_email = models.ForeignKey(CustomerEmail, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name_plural = "Campaign Recipients"

class CampaignImage(models.Model):
    campaign = models.ForeignKey(
        'EmailCampaign',  # Use string reference if EmailCampaign is defined later
        on_delete=models.CASCADE,
        related_name='images',
        blank=True,
        null=True,
    )
    image = models.ImageField(
        upload_to='campaign_images/',
        storage=GoogleCloudMediaFileStorage(),  # Explicitly specify storage
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])]
    )
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Campaign Images"
    
    def __str__(self):
        return f"Image: {self.alt_text or self.image.name}"

