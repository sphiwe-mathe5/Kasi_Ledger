from django.utils import timezone
from django.db.models import Count, Q, Sum
from datetime import timedelta
from .models import StyleTicket, Booking
from submit.models import Subscription
from core.models import StockImage

def get_user_subscription_status(user):
    """
    Get detailed subscription status for a user.
    Returns dict with subscription info and permission flags.
    """
    try:
        subscription = Subscription.objects.get(user=user)
        now = timezone.now()
        
        # Determine if subscription is in trial
        is_trialing = subscription.status == 'trialing' and subscription.trial_end_date
        trial_expired = is_trialing and subscription.trial_end_date <= now
        
        # Determine effective plan
        if is_trialing and not trial_expired:
            effective_plan = 'trial'
            display_plan = 'Free Trial'
        elif is_trialing and trial_expired:
            effective_plan = 'free'
            display_plan = 'Free'
        else:
            effective_plan = subscription.plan.name.lower().replace(' ', '_')
            display_plan = subscription.plan.name
        
        # Calculate days left (for trial only)
        days_left = None
        if is_trialing and not trial_expired:
            days_left = (subscription.trial_end_date - now).days
        
        return {
            'subscription': subscription,
            'is_active': subscription.is_active(),
            'is_trialing': is_trialing,
            'trial_expired': trial_expired,
            'effective_plan': effective_plan,  # 'trial', 'free', 'growth_plan', 'business_pro'
            'display_plan': display_plan,
            'days_left': days_left,
            'plan_name': subscription.plan.name,
            'status': subscription.status,
            'next_payment': subscription.next_payment_date,
        }
    
    except Subscription.DoesNotExist:
        return {
            'subscription': None,
            'is_active': False,
            'is_trialing': False,
            'trial_expired': False,
            'effective_plan': None,
            'display_plan': None,
            'days_left': None,
            'plan_name': None,
            'status': None,
            'next_payment': None,
        }


def check_feature_access(user, feature):
    """
    Check if user can access a specific feature based on subscription.
    
    Features:
    - 'appointments': Create/view appointments
    - 'chatbot': Use AI chatbot
    - 'bookings_view': View bookings (owner only)
    - 'bookings_create': Create bookings (public)
    - 'advanced_analytics': View analytics
    - 'worker_management': Manage workers
    - 'salon_profile': Access salon profile
    - 'email_marketing': Send marketing emails
    - 'ai_image_recognition': Use AI image recognition
    
    Returns: {'allowed': bool, 'message': str, 'limit': int|None, 'current': int|None}
    """
    sub_status = get_user_subscription_status(user)
    
    if not sub_status['subscription']:
        return {
            'allowed': False,
            'message': 'No active subscription. Please select a plan.',
            'feature': feature,
            'reason': 'no_subscription'
        }
    
    effective_plan = sub_status['effective_plan']
    now = timezone.now()
    
    # TRIAL FEATURES - All access during trial
    if effective_plan == 'trial':
        return {
            'allowed': True,
            'message': f'Feature available. Trial ends in {sub_status["days_left"]} days.',
            'feature': feature,
            'trial_days_left': sub_status['days_left']
        }
    
    # FREE FEATURES - Limited access after trial expires
    elif effective_plan == 'free':
        
        if feature == 'appointments':
            # Free: 30 appointments per month limit
            start_of_month = now.replace(day=1)
            month_count = (
                StyleTicket.objects.filter(
                    created_by=user,
                    created_at__gte=start_of_month
                ).count() +
                Booking.objects.filter(
                    salon__user=user,
                    booking_date__gte=start_of_month,
                    status='completed'
                ).count()
            )
            
            limit = 30
            if month_count >= limit:
                return {
                    'allowed': False,
                    'message': f'You\'ve reached the 30 appointment limit for this month.',
                    'feature': feature,
                    'limit': limit,
                    'current': month_count,
                    'reason': 'limit_exceeded'
                }
            
            return {
                'allowed': True,
                'message': f'Free plan: {limit - month_count} appointments remaining this month.',
                'feature': feature,
                'limit': limit,
                'current': month_count,
            }
        
        elif feature == 'chatbot':
            # Free: No chatbot access
            return {
                'allowed': False,
                'message': 'AI Chatbot requires Growth Plan or higher.',
                'feature': feature,
                'reason': 'plan_restriction'
            }
        
        elif feature == 'email_marketing':
            # Free: No email marketing
            return {
                'allowed': False,
                'message': 'Email marketing requires Growth Plan or higher.',
                'feature': feature,
                'reason': 'plan_restriction'
            }
        
        elif feature == 'bookings_view':
            # Free: Cannot view bookings
            return {
                'allowed': False,
                'message': 'Bookings management requires Business Pro plan.',
                'feature': feature,
                'reason': 'plan_restriction'
            }
        
        elif feature == 'bookings_create':
            # Free: Public cannot book
            return {
                'allowed': False,
                'message': 'Salon must have Growth Plan or higher to accept bookings.',
                'feature': feature,
                'reason': 'plan_restriction'
            }
        
        elif feature == 'advanced_analytics':
            # Free: No advanced analytics
            return {
                'allowed': False,
                'message': 'Advanced analytics requires Business Pro plan.',
                'feature': feature,
                'reason': 'plan_restriction'
            }

        elif effective_plan == 'free':
        
            if feature == 'ai_image_recognition':
                # Free: 10 uploads per month limit
                start_of_month = now.replace(day=1)
                month_count = StockImage.objects.filter(
                    user=user,
                    created_at__gte=start_of_month
                ).count()
                
                limit = 10
                if month_count >= limit:
                    return {
                        'allowed': False,
                        'message': f'You\'ve reached the 10 image recognition limit for this month.',
                        'feature': feature,
                        'limit': limit,
                        'current': month_count,
                        'reason': 'limit_exceeded'
                    }
            
            return {
                'allowed': True,
                'message': f'Free plan: {limit - month_count} image recognitions remaining this month.',
                'feature': feature,
                'limit': limit,
                'current': month_count,
            }
        
        else:
            # Other features available on free
            return {
                'allowed': True,
                'message': 'Feature available on Free plan.',
                'feature': feature,
            }
    
    # GROWTH PLAN FEATURES
    elif effective_plan == 'growth_plan':
        
        if feature == 'chatbot':
            return {'allowed': True, 'message': 'AI Chatbot available.', 'feature': feature}
        
        elif feature == 'email_marketing':
            return {'allowed': True, 'message': 'Email marketing available.', 'feature': feature}
        
        elif feature == 'bookings_create':
            return {'allowed': True, 'message': 'Public bookings enabled.', 'feature': feature}
        
        elif feature == 'bookings_view':
            return {
                'allowed': False,
                'message': 'Bookings management requires Business Pro plan.',
                'feature': feature,
                'reason': 'plan_restriction'
            }
        
        elif feature == 'advanced_analytics':
            return {
                'allowed': False,
                'message': 'Advanced analytics requires Business Pro plan.',
                'feature': feature,
                'reason': 'plan_restriction'
            }
    
        elif effective_plan == 'growth_plan':
            if feature == 'ai_image_recognition':
                return {
                    'allowed': True,
                    'message': 'Unlimited image recognition available.',
                    'feature': feature,
                    'unlimited': True
                }
        
        else:
            return {'allowed': True, 'message': 'Feature available.', 'feature': feature}
    
    # BUSINESS PRO FEATURES - Full access
    elif effective_plan == 'business_pro':
        return {
            'allowed': True,
            'message': 'Feature available. Full access granted.',
            'feature': feature
        }

    elif effective_plan == 'business_pro':
        if feature == 'ai_image_recognition':
            return {
                'allowed': True,
                'message': 'Unlimited image recognition available.',
                'feature': feature,
                'unlimited': True
            }
    
    return {
        'allowed': False,
        'message': 'Unable to determine access.',
        'feature': feature,
        'reason': 'unknown_plan'
    }


def can_access_salon_dashboard(user):
    """Check if user can access salon dashboard"""
    sub_status = get_user_subscription_status(user)
    
    if not sub_status['subscription']:
        return False, 'No subscription'
    
    # Trial and active subscriptions can access
    if sub_status['is_active']:
        return True, 'Active'
    
    # If not active but is a free plan (not trial), they can access with limited features
    if sub_status['effective_plan'] == 'free' and sub_status['trial_expired']:
        return True, 'Free (limited)'
    
    return False, 'Subscription expired or cancelled'