# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser, Profile, SubscriptionPlan, Subscription

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


@receiver(post_save, sender=CustomUser)
def create_trial_subscription(sender, instance, created, **kwargs):
    if created:
        # Assuming you have a default plan for trials
        trial_plan = SubscriptionPlan.objects.get(name='Free')
        Subscription.objects.create(
            user=instance,
            plan=trial_plan,
            status='trialing',
            trial_end_date=timezone.now() + timedelta(days=30))