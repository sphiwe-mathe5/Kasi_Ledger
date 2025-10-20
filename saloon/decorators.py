from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from .subscriptions import can_access_salon_dashboard, check_feature_access
from django.http import HttpResponseForbidden

def subscription_required(feature=None):
    """
    Decorator to enforce subscription requirements on views.
    
    feature: The feature to check access for
    Example: @subscription_required(feature='appointments')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # If specific feature check
            if feature:
                access = check_feature_access(request.user, feature)
                if not access['allowed']:
                    messages.error(request, access['message'])
                    return redirect('subscription_plans')
            else:
                # Just check if has any active subscription
                can_access, reason = can_access_salon_dashboard(request.user)
                if not can_access:
                    messages.error(request, 'Your subscription is not active. Please upgrade.')
                    return redirect('subscription_plans')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def company_category_required(*allowed_categories):
    """
    Restrict access so that only users whose company_category matches `view_category`
    can access the view. All others are redirected to the console page.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return redirect('login')

            if user.company_category in allowed_categories:
                return view_func(request, *args, **kwargs)

            return redirect('console')  # anyone else goes to console

        return _wrapped_view
    return decorator