from django.db import models
from django.contrib.auth.models import User
from PIL import Image
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import AbstractUser
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
import uuid
from datetime import timedelta
from submit.managers import CustomUserManager
from django.utils.crypto import get_random_string
from django.utils import timezone


PRICING_CHOICES = [
    ('free', 'Free Trial'),
    ('basic', 'Basic'),
    ('premium', 'Premium'),
]



class CustomUser(AbstractUser):
    username = models.CharField(max_length=100, unique=True, default='none')
    email = models.EmailField(max_length=255, unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    is_authorized = models.BooleanField(default=False)
    login_token = models.CharField(max_length=6, blank=True, null=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    transaction_pin_hash = models.CharField(max_length=128, blank=True, default='')
    company_category = models.CharField(
        max_length=20,
        choices=[
            ('restaurant', 'Restaurant'),
            ('clothing_brand', 'Clothing Brand'),
            ('spaza', 'Spaza'),
            ('salon', 'Salon'),
            ('car_wash', 'Car Wash'),
        ],
        blank=True,
        null=True
    )

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_groups',  
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions',  
        blank=True
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []


    def is_verified(self):

        return True
        
    def __str__(self):
        return self.email
    
    def has_transaction_pin(self):
        """Check if user has set a transaction PIN"""
        return bool(self.transaction_pin_hash)
    
    def set_transaction_pin(self, pin):
        """Set the transaction PIN"""
        self.transaction_pin_hash = make_password(pin)
        self.save()
    
    def check_transaction_pin(self, pin):
        """Verify the transaction PIN"""
        if not self.transaction_pin_hash:
            return False
        return check_password(pin, self.transaction_pin_hash)
    
    def remove_transaction_pin(self):
        """Remove the transaction PIN"""
        self.transaction_pin_hash = ''
        self.save()


class PasswordResetRequest(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.CharField(max_length=32, default=get_random_string(32), editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    
    
    TOKEN_VALIDITY_PERIOD = timezone.timedelta(hours=1)

    def is_valid(self):
        return timezone.now() <= self.created_at + self.TOKEN_VALIDITY_PERIOD

    def send_reset_email(self):
        reset_link = f"http://localhost:8000/reset-password/{self.token}/"
        send_mail(
            'Password Reset Request',
            f'Click the following link to reset your password: {reset_link}',
            settings.DEFAULT_FROM_EMAIL,
            [self.email],
            fail_silently=False,
        )



class AdminPasswordResetRequest(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.CharField(max_length=32, default=get_random_string(32), editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    
    TOKEN_VALIDITY_PERIOD = timezone.timedelta(hours=1)

    def is_valid(self):
        return timezone.now() <= self.created_at + self.TOKEN_VALIDITY_PERIOD

    def send_reset_email(self):
        reset_link = f"http://localhost:8000/reset-password/{self.token}/"
        send_mail(
            'Admin Password Reset Request',
            f'Click the following link to reset the admin password: {reset_link}',
            settings.DEFAULT_FROM_EMAIL,
            [self.email],
            fail_silently=False,
        )


        
class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    is_paid = models.BooleanField(default=False)
    pricing_plan = models.CharField(max_length=10, choices=PRICING_CHOICES, default='free')
    company_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f'{self.user.email} Profile'


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    features = models.JSONField()
    is_active = models.BooleanField(default=True)
    paystack_plan_code = models.CharField(max_length=100, blank=True)
    product_limit = models.IntegerField(default=3)
    
    def __str__(self):
        return f"{self.name} - R{self.price}/month"

class Subscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('past_due', 'Past Due'),
        ('unpaid', 'Unpaid'),
        ('trialing', 'Trialing'),  # Add a new status for trial
    )

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    paystack_subscription_code = models.CharField(max_length=100, blank=True)
    paystack_email_token = models.CharField(max_length=100, blank=True)
    next_payment_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)  # Add this field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_active(self):
        if self.status == 'trialing' and self.trial_end_date > timezone.now():
            return True
        return (
            self.status == 'active' and 
            (self.next_payment_date is None or self.next_payment_date > timezone.now())
        )

    def cancel(self):
        if self.status == 'active':
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.save()
    
    def activate(self):
        if self.status == 'cancelled':
            self.status = 'active'
            self.cancelled_at = None
            self.save()

class PaymentHistory(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paystack_reference = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    paid_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class ProductPeriod(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    product_count = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=30)
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_current_period(cls, profile):
        current_date = timezone.now()
        current_period = cls.objects.filter(
            profile=profile,
            start_date__lte=current_date,
            end_date__gte=current_date
        ).first()

        if not current_period:
            current_period = cls.objects.create(
                profile=profile,
                start_date=current_date,
                end_date=current_date + timedelta(days=30)
            )
        return current_period