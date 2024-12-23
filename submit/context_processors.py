
from .models import Subscription

def subscription_status(request):
    if request.user.is_authenticated:
        try:
            subscription = Subscription.objects.get(user=request.user)
            return {
                'user_subscription': {
                    'plan': subscription.plan.name,
                    'status': subscription.status,
                    'is_active': subscription.is_active(),
                    'next_payment': subscription.next_payment_date
                }
            }
        except Subscription.DoesNotExist:
            return {'user_subscription': {'plan': 'Free', 'status': 'inactive'}}
    return {'user_subscription': None}