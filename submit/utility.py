from django.utils import timezone
from submit.models import SubscriptionPlan, Subscription

def delete_expired_free_trials(user):
    """
    Delete expired free trial subscriptions for the given user.
    """
    expired_subscriptions = Subscription.objects.filter(
        user=user,
        status='trialing',
        trial_end_date__lte=timezone.now()  # Trial has ended
    )
    expired_subscriptions.delete()