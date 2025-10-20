from django.shortcuts import redirect
from django.urls import reverse
from social_core.exceptions import AuthException

def save_profile_data(strategy, details, backend, user=None, *args, **kwargs):
    """Save basic profile data from Google"""
    if user:
        # Update user with Google data
        user.first_name = details.get('first_name', '')
        user.last_name = details.get('last_name', '')
        if not user.email:  # Only set if not already set
            user.email = details.get('email', '')
        user.save()
    return {'user': user}

def redirect_to_complete_profile(strategy, details, backend, user=None, *args, **kwargs):
    """Redirect to complete profile if company details are missing"""
    if user and (not user.company_name or not user.company_category):
        # Store user ID in session for the complete profile form
        strategy.session_set('incomplete_user_id', user.id)
        return redirect('complete_profile')
    # If profile is complete → return None, so the pipeline continues normally
    return None


def redirect_based_on_category(user):
    """Redirects based on company category, or forces profile completion."""
    # Force completion if profile missing
    if not user.company_name or not user.company_category:
        return redirect("complete_profile")

    if user.company_category == "salon":
        return redirect("saloon:saloon")
    elif user.company_category in ["restaurant", "clothing_brand", "spaza"]:
        return redirect("console")
    elif user.company_category == "car_wash":
        return redirect("dashboard")
    
    return redirect("console")
