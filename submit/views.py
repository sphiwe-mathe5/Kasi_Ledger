from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .forms import SearchForm
from .models import Profile, ProductPeriod
from django.utils import timezone
import json
import datetime
from django.views.decorators.http import require_POST
import hmac
from datetime import timedelta
import hashlib
from submit.utility import delete_expired_free_trials
import logging
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from submit.models import SubscriptionPlan, Subscription, PaymentHistory
from django.conf import settings
import requests
from django.db.models import Q
from django.db import models
from django.db import transaction
from .models import User
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser, PasswordResetRequest, AdminPasswordResetRequest
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.sites.shortcuts import get_current_site
import re
from django.contrib.auth import update_session_auth_hash

#Authentication VIEWS
def login_view(request):
    if request.method == 'POST':
        # Check if this is a social auth redirect
        if 'google-oauth2' in request.path:
            return redirect('social:begin', backend='google-oauth2')
        
        # Verify reCAPTCHA for regular login
        recaptcha_token = request.POST.get('recaptcha_token')
        data = {
            'secret': settings.RECAPTCHA_PRIVATE_KEY,
            'response': recaptcha_token
        }
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = r.json()

        if not result['success'] or result['score'] < 0.5:
            messages.error(request, 'reCAPTCHA verification failed. Please try again.')
            return redirect('login')

        username = request.POST['username']  # <-- can be email or phone
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect_based_on_category(user)
        else:
            messages.error(request, 'Invalid credentials')

    return render(request, 'submit/login.html', {
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
    })

def redirect_based_on_category(user):
    """Helper function to redirect based on company category"""
    # If profile incomplete, force profile completion
    if not user.company_name or not user.company_category:
        return redirect("complete_profile")
    
    if user.company_category == "salon":
        return redirect("saloon:saloon")
    elif user.company_category in ["restaurant", "clothing_brand", "spaza"]:
        return redirect("console")
    elif user.company_category == "car_wash":
        return redirect("dashboard")
    
    return redirect("console")


def is_valid_email(value):
    # Simple email pattern
    return re.match(r"[^@]+@[^@]+\.[^@]+", value)

def is_valid_phone_number(value):
    # Allow formats like +1234567890, 123-456-7890, (123) 456-7890, etc.
    digits_only = re.sub(r'\D', '', value)  # Strip all non-digit characters
    return 7 <= len(digits_only) <= 15  # Basic length check


def signup_view(request):
    if request.method == 'POST':

        if 'google-oauth2' in request.path:
            return redirect('social:begin', backend='google-oauth2')
        # Verify reCAPTCHA
        recaptcha_token = request.POST.get('recaptcha_token')
        data = {
            'secret': settings.RECAPTCHA_PRIVATE_KEY,
            'response': recaptcha_token
        }
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = r.json()

        # Check if the reCAPTCHA verification fails or score is below threshold
        if not result['success'] or result['score'] < 0.5:
            messages.error(request, 'reCAPTCHA verification failed. Please try again.')
            return redirect('signup')

        # Continue processing only if reCAPTCHA is successful

        company_name = request.POST['company_name']
        company_category = request.POST['company_category']
        username = request.POST.get('username', '').strip()
        password = request.POST['password']

        email = None
        phone_number = None

        # Determine if input is valid email or phone
        if is_valid_email(username):
            email = username
        elif is_valid_phone_number(username):
            # Optionally normalize phone number by removing symbols
            phone_number = re.sub(r'\D', '', username)
        else:
            messages.error(request, 'Please enter a valid email or phone number.')
            return redirect('signup')

        try:
            # Create the user
            user = CustomUser.objects.create_user(
                username=email or phone_number,  # Django requires something here
                email=email if email else None,
                phone_number=phone_number if phone_number else None,
                company_category=company_category,
                company_name=company_name,
                password=password,
            )

            # Send a welcome email
            current_site = get_current_site(request)
            context = {
                'user': user,
                'company_name': company_name,
                'domain': settings.SITE_URL,
            }
            html_message = render_to_string('submit/welcome.html', context)
            plain_message = strip_tags(html_message)
            send_mail(
                subject=f'Thank You For Signing Up',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )

            # Log the user in and redirect to the index page
            login(request, user, backend='submit.backends.EmailOrPhoneBackend')
            return redirect('index')

        except IntegrityError:
            messages.error(request, 'An account with this email or phone already exists. Please log in or use a different one.')
            return redirect_based_on_category(user)  

    return render(request, 'submit/register.html', {
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
    })


from submit.pipeline import redirect_based_on_category
def complete_profile_view(request):
    """Complete profile after Google OAuth"""
    # Get user from session (set in pipeline)
    user_id = request.session.get('incomplete_user_id')
    if not user_id:
        if request.user.is_authenticated:
            user = request.user
        else:
            return redirect('login')
    else:
        user = get_object_or_404(CustomUser, id=user_id)
    
    # If profile is already complete, redirect appropriately
    if user.company_name and user.company_category:
        return redirect_based_on_category(user)
    
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        company_category = request.POST.get('company_category')
        #admin_password = request.POST.get('admin_password')
        
        if company_name and company_category:
            # Update user with company details
            user.company_name = company_name
            user.company_category = company_category
            #user.admin_password = admin_password
            user.save()
            
            # Clear session
            if 'incomplete_user_id' in request.session:
                del request.session['incomplete_user_id']
            
            # Log in user if not already logged in
            if not request.user.is_authenticated:
                from django.contrib.auth import login
                login(request, user, backend='social_core.backends.google.GoogleOAuth2')
            
            messages.success(request, 'Profile completed successfully!')
            
            # Redirect based on company category
            if company_category == "salon":
                return redirect("saloon:saloon")
            elif company_category == "restaurant":
                return redirect("console")
            elif company_category == "clothing_brand":
                return redirect("console")
            elif company_category == "spaza":
                return redirect("console")
            elif company_category == "car_wash":
                return redirect("dashboard")
            else:
                return redirect('console')
        else:
            messages.error(request, 'All fields are required.')
    
    # Get Google profile picture if available
    google_picture = None
    try:
        if user.social_auth.exists():
            social_user = user.social_auth.get(provider='google-oauth2')
            google_picture = social_user.extra_data.get('picture')
    except:
        pass
    
    context = {
        'user': user,
        'google_picture': google_picture,
        'COMPANY_CATEGORIES': [
            ('restaurant', 'Restaurant'),
            ('clothing_brand', 'Clothing Brand'),
            ('spaza', 'Spaza'),
            ('salon', 'Salon'),
            ('car_wash', 'Car Wash'),
        ]
    }
    
    return render(request, 'submit/complete_profile.html', context)

def forgot_password_view(request):
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_token = request.POST.get('recaptcha_token')
        data = {
            'secret': settings.RECAPTCHA_PRIVATE_KEY,
            'response': recaptcha_token
        }
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = r.json()

        if not result.get('success', False) or result.get('score', 0) < 0.5:
            messages.error(request, 'Verification failed. Please try again.')
            return render(request, 'submit/login.html')

        email = request.POST['email']
        user = CustomUser.objects.filter(email=email).first()

        if user:
            token = get_random_string(32)
            reset_request = PasswordResetRequest.objects.create(user=user, email=email, token=token)
            reset_request.send_reset_email()
            messages.success(request, 'Reset link sent to your email.')
        else:
            messages.error(request, 'Email not found.')

    return render(request, 'submit/login.html', {
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
    })


def reset_password_view(request, token):
    reset_request = PasswordResetRequest.objects.filter(token=token).first()

    if not reset_request or not reset_request.is_valid():
        messages.error(request, 'Invalid or expired reset link')
        return redirect('index')

    if request.method == 'POST':
        new_password = request.POST['new_password']
        reset_request.user.set_password(new_password)
        reset_request.user.save()
        messages.success(request, 'Password reset successful')
        return redirect('login')

    return render(request, 'submit/reset_password.html', {'token': token})


def forgot_admin_password_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        user = CustomUser.objects.filter(email=email).first()

        if user:
            token = get_random_string(32)
            reset_request = AdminPasswordResetRequest.objects.create(user=user, email=email, token=token)
            reset_request.send_reset_email()
            messages.success(request, 'Admin password reset link sent to your email.')
        else:
            messages.error(request, 'Email not found.')

    return render(request, 'submit/forgot_admin_password.html')


def reset_admin_password_view(request, token):
    reset_request = AdminPasswordResetRequest.objects.filter(token=token).first()

    if not reset_request or not reset_request.is_valid():
        messages.error(request, 'Invalid or expired reset link.')
        return redirect('contact')

    if request.method == 'POST':
        new_admin_password = request.POST['new_admin_password']
        reset_request.user.admin_password = new_admin_password
        reset_request.user.save()
        messages.success(request, 'Admin password reset successful.')
        return redirect('contact')  

    return render(request, 'submit/reset_admin_password.html', {'token': token})


def reset_password_view(request, token):
    reset_request = PasswordResetRequest.objects.filter(token=token).first()

    if not reset_request or not reset_request.is_valid():
        messages.error(request, 'Invalid or expired reset link')
        return redirect('index')

    if request.method == 'POST':
        new_password = request.POST['new_password']
        reset_request.user.set_password(new_password)
        reset_request.user.save()
        messages.success(request, 'Password reset successful')
        return redirect('login')

    return render(request, 'submit/reset_password.html', {'token': token})

@login_required
def transaction_pin_settings(request):
    """View to manage transaction PIN"""
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'set_pin':
            pin = request.POST.get('pin', '').strip()
            confirm_pin = request.POST.get('confirm_pin', '').strip()
            
            # Validate PIN
            if not pin:
                messages.error(request, "Please enter a PIN.")
            elif len(pin) < 4:
                messages.error(request, "PIN must be at least 4 characters long.")
            elif pin != confirm_pin:
                messages.error(request, "PINs do not match.")
            else:
                # Set the PIN
                user.set_transaction_pin(pin)
                messages.success(request, "Transaction PIN set successfully!")
                return redirect('contact')
        
        elif action == 'remove_pin':
            user.remove_transaction_pin()
            # Clear any active session
            if 'transactions_unlocked' in request.session:
                del request.session['transactions_unlocked']
            messages.success(request, "Transaction PIN removed successfully!")
            return redirect('contact')
    
    return render(request, 'submit/transaction_pin_settings.html', {
        'has_pin': user.has_transaction_pin()
    })


def logout_view(request):
    logout(request)

    return redirect('index')


@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)

        if u_form.is_valid():
            u_form.save()
            messages.success(request, f'updated!')
            return redirect('profile')

    else:
        u_form = UserUpdateForm(instance=request.user)

    context = {'u_form': u_form}

    return render(request, 'submit/profile.html', context)


@login_required
def update_profile(request):
    user = request.user

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        company_category = request.POST.get('company_category', '').strip()

        # Optional: Validate inputs here

        # Update user fields
        user.first_name = first_name
        user.last_name = last_name
        user.username = username
        user.email = email
        user.phone_number = phone_number
        user.company_name = company_name
        user.company_category = company_category

        try:
            user.save()
            messages.success(request, 'Profile updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')

        return redirect('profile')  # Update this name to match your URL

    return render(request, 'submit/profile.html', {'user': user}) 


@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        user = request.user

        # Check if current password is correct
        if not user.check_password(current_password):
            messages.error(request, 'Your current password is incorrect.')
            return redirect('profile')

        # Check if new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return redirect('profile')

        # Optional: Enforce password strength (length, complexity, etc.)
        if len(new_password) < 8:
            messages.error(request, 'New password must be at least 8 characters long.')
            return redirect('profile')

        # Set new password
        user.set_password(new_password)
        user.save()

        # Keep the user logged in after password change
        update_session_auth_hash(request, user)

        messages.success(request, 'Your password has been changed successfully.')
        return redirect('profile')  # Or wherever you want to redirect after success

    return render(request, 'submit/profile.html')  # Use your actual template name

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, "Your account has been deleted.")
        return redirect('index')  # Or wherever you want to redirect after deletion

    messages.error(request, "Invalid request method.")
    return redirect('profile')  # Redirect if user accessed via GET

@login_required
def subscription_plans(request):
    # Delete expired free trial subscriptions for the current user
    delete_expired_free_trials(request.user)

    # Exclude the free plan (if price == 0)
    plans = SubscriptionPlan.objects.filter(is_active=True).exclude(price=0)

    # Handle plan selection (if plan_id is passed via GET)
    plan_id = request.GET.get('plan_id')
    if plan_id:
        # Get the selected plan
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)

        # Get or create the user's subscription
        subscription, created = Subscription.objects.get_or_create(user=request.user)

        # Update the subscription with the new plan and status
        subscription.plan = plan
        subscription.status = 'active'  # Set status to active for paid plans
        subscription.trial_end_date = None  # Clear the trial end date (if any)
        subscription.save()

        # Display a success message
        messages.success(request, f"You have successfully subscribed to the {plan.name} plan.")
        return redirect('subscription_settings')

    # Render the subscription plans page
    return render(request, 'submit/subscription_plans.html', {'plans': plans})



logger = logging.getLogger(__name__)

@login_required
def initialize_payment(request, plan_id):
    try:
        local_plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        
        plan_check = requests.get(
            f"https://api.paystack.co/plan/{local_plan.paystack_plan_code}",
            headers=headers
        )
        
        print(f"Plan check response: {plan_check.text}")
        
        
        if plan_check.status_code != 200:
            plan_data = {
                "name": local_plan.name,
                "amount": int(float(local_plan.price) * 100),  
                "interval": "monthly",
                "currency": "ZAR",
                "description": local_plan.description
            }
            
            plan_response = requests.post(
                "https://api.paystack.co/plan",
                headers=headers,
                json=plan_data
            )
            
            print(f"Plan creation response: {plan_response.text}")
            
            if plan_response.status_code == 200:
                plan_data = plan_response.json().get('data', {})
                
                local_plan.paystack_plan_code = plan_data.get('plan_code')
                local_plan.save()
            else:
                raise Exception("Failed to create Paystack plan")

        
        transaction_data = {
            "email": request.user.email,
            "amount": int(float(local_plan.price) * 100),
            "plan": local_plan.paystack_plan_code,
            "currency": "ZAR",
            "callback_url": f"{settings.SITE_URL}/payment/callback/",
            "metadata": {
                "plan_id": plan_id,
                "user_id": request.user.id,
                "custom_fields": [
                    {
                        "display_name": "Plan Name",
                        "variable_name": "plan_name",
                        "value": local_plan.name
                    }
                ]
            }
        }
        
        print(f"Transaction data: {transaction_data}")
        
        init_response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers,
            json=transaction_data
        )
        
        print(f"Transaction init response: {init_response.text}")
        
        if init_response.status_code == 200:
            return JsonResponse(init_response.json())
        
        return JsonResponse({
            "error": init_response.json().get('message', 'Payment initialization failed')
        }, status=400)
        
    except Exception as e:
        print(f"Payment initialization error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def webhook(request):
    try:
        print("Webhook received")
        paystack_signature = request.headers.get("X-Paystack-Signature")
        
        if not paystack_signature:
            print("No Paystack signature")
            return HttpResponse(status=400)

        
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()
        
        if computed_signature != paystack_signature:
            print("Invalid signature")
            return HttpResponse(status=400)

        payload = json.loads(request.body)
        print(f"Webhook payload: {payload}")
        
        event = payload.get('event')
        data = payload.get('data', {})
        
        if event == 'subscription.create':
            try:
                
                customer_email = data.get('customer', {}).get('email')
                
                
                try:
                    user = CustomUser.objects.get(email=customer_email)
                except CustomUser.DoesNotExist:
                    print(f"User not found for email: {customer_email}")
                    return HttpResponse(status=400)

                
                plan_data = data.get('plan', {})
                try:
                    plan = SubscriptionPlan.objects.get(paystack_plan_code=plan_data.get('plan_code'))
                except SubscriptionPlan.DoesNotExist:
                    print(f"Plan not found for code: {plan_data.get('plan_code')}")
                    return HttpResponse(status=400)

                
                subscription = Subscription.objects.get_or_create(
                    user=user,
                    defaults={'plan': plan}
                )[0]

                
                subscription.status = 'active'
                subscription.paystack_subscription_code = data.get('subscription_code')
                subscription.paystack_email_token = data.get('email_token')
                
                
                next_payment_str = data.get('next_payment_date')
                if next_payment_str:
                    
                    next_payment_date = datetime.datetime.strptime(
                        next_payment_str.split('.')[0], 
                        '%Y-%m-%dT%H:%M:%S'
                    )
                    next_payment_date = timezone.make_aware(next_payment_date)
                    subscription.next_payment_date = next_payment_date
                
                subscription.save()
                
                print(f"Updated subscription: {subscription.id} with next payment date: {subscription.next_payment_date}")

            except Exception as e:
                print(f"Error processing {event}: {str(e)}")
                return HttpResponse(status=500)
            
        return HttpResponse(status=200)
        
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return HttpResponse(status=500)

def send_payment_success_email(subscription_id):
    subscription = Subscription.objects.get(id=subscription_id)
    subject = 'Payment Successful'
    html_message = render_to_string('submit/emails/payment_success.html', {
        'subscription': subscription
    })
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = subscription.user.email
    send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

def handle_successful_charge(payload):
    with transaction.atomic():
        data = payload.get('data', {})
        metadata = data.get('metadata', {})
        user_id = metadata.get('user_id')
        plan_id = metadata.get('plan_id')
        
        if not all([user_id, plan_id]):
            logger.error("Missing required metadata in webhook")
            return HttpResponseBadRequest()

        try:
            subscription = Subscription.objects.select_for_update().get_or_create(
                user_id=user_id,
                defaults={'plan_id': plan_id}
            )[0]
            
            
            next_payment = timezone.now() + timezone.timedelta(days=30)
            
            subscription.status = 'active'
            subscription.paystack_subscription_code = data.get('reference')
            subscription.next_payment_date = next_payment
            subscription.save()

            PaymentHistory.objects.create(
                subscription=subscription,
                amount=Decimal(data.get('amount', 0)) / 100,
                paystack_reference=data.get('reference'),
                status=data.get('status'),
                paid_at=timezone.now()
            )
            
            # Send email directly instead of using delay
            send_payment_success_email(subscription.id)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing successful charge: {str(e)}")
            return HttpResponse(status=500)


 
def payment_callback(request):
    reference = request.GET.get('reference')
    trxref = request.GET.get('trxref')
    
    
    print(f"Payment callback received - Reference: {reference}")
    
    
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    verify_url = f"https://api.paystack.co/transaction/verify/{reference}"
    response = requests.get(verify_url, headers=headers)
    
    if response.status_code == 200:
        response_data = response.json()
        if response_data['status'] and response_data['data']['status'] == 'success':
            messages.success(request, "Payment successful! Your subscription is being processed.")
        else:
            messages.error(request, "Payment verification failed.")
    else:
        messages.error(request, "Could not verify payment.")
    
    return redirect('subscription_settings')

@login_required
def cancel_subscription(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()
        
    try:
        subscription = Subscription.objects.get(
            user=request.user,
            status='active'
        )
        
        
        print(f"Subscription code in database: {subscription.paystack_subscription_code}")
        
        if not subscription.paystack_subscription_code:
            raise ValueError("No subscription code found")
            
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        
        list_response = requests.get(
            "https://api.paystack.co/subscription",
            headers=headers
        )
        
        print(f"List subscriptions response: {list_response.text}")
        
        if list_response.status_code == 200:
            subscriptions = list_response.json().get('data', [])
            
            customer_sub = next(
                (sub for sub in subscriptions if sub.get('customer', {}).get('email') == request.user.email),
                None
            )
            
            if customer_sub:
                subscription_code = customer_sub.get('subscription_code')
                print(f"Found subscription code from Paystack: {subscription_code}")
                
                
                response = requests.post(
                    "https://api.paystack.co/subscription/disable",
                    headers=headers,
                    json={
                        "code": subscription_code,
                        "token": customer_sub.get('email_token')
                    }
                )
                
                print(f"Cancel response: {response.text}")
                
                if response.status_code == 200:
                    subscription.cancel()
                    messages.success(request, "Your subscription has been cancelled.")
                else:
                    raise Exception(f"Paystack API error: {response.text}")
            else:
                raise Exception("No active subscription found on Paystack")
                
        return redirect('subscription_settings')
            
    except Subscription.DoesNotExist:
        messages.error(request, "No active subscription found.")
    except Exception as e:
        print(f"Subscription cancellation error: {str(e)}")
        messages.error(request, "An error occurred. Please contact support.")
    
    return redirect('subscription_settings')



def activate_subscription(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()
        
    try:
        subscription = Subscription.objects.get(
            user=request.user,
            status='cancelled'
        )
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        
        create_response = requests.post(
            "https://api.paystack.co/subscription",
            headers=headers,
            json={
                "customer": request.user.email,
                "plan": subscription.plan.paystack_plan_code
            }
        )
        
        if create_response.status_code == 200:
            subscription_data = create_response.json().get('data', {})
            subscription.paystack_subscription_code = subscription_data.get('subscription_code')
            subscription.activate()
            messages.success(request, "Your subscription has been reactivated.")
        else:
            raise Exception(f"Paystack API error: {create_response.text}")
            
    except Subscription.DoesNotExist:
        messages.error(request, "No cancelled subscription found.")
    except Exception as e:
        print(f"Subscription activation error: {str(e)}")
        messages.error(request, "An error occurred. Please contact support.")
    
    return redirect('subscription_settings')

def delete_subscription(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()
        
    try:
        subscription = Subscription.objects.get(
            user=request.user
        )
        
        
        if subscription.status != 'cancelled':
            messages.error(request, "Please cancel your subscription before deleting it.")
            return redirect('subscription_settings')
            
        subscription.delete()
        messages.success(request, "Your subscription has been deleted.")
            
    except Subscription.DoesNotExist:
        messages.error(request, "No subscription found.")
    except Exception as e:
        print(f"Subscription deletion error: {str(e)}")
        messages.error(request, "An error occurred. Please contact support.")
    
    return redirect('subscription_settings')

@login_required
def subscription_settings(request):

    delete_expired_free_trials(request.user)

    try:
        # Get the user's subscription
        subscription = Subscription.objects.get(user=request.user)

        # Debug: Print subscription details
        print(f"Subscription Plan: {subscription.plan.name}, Status: {subscription.status}")

        # Check if the trial has ended
        days_left = None
        if subscription.status == 'trialing':
            now = timezone.now()
            if subscription.trial_end_date > now:
                days_left = (subscription.trial_end_date - now).days
            else:
                messages.warning(request, "Your free trial has ended. Please subscribe to a plan.")
                return redirect('subscription_plans')

        # Fetch payment history for the subscription
        payment_history = PaymentHistory.objects.filter(
            subscription=subscription
        ).order_by('-paid_at')

        # Prepare context for the template
        context = {
            'subscription': subscription,
            'payment_history': payment_history,
            'current_plan': subscription.plan.name,  
            'status': subscription.status,  
            'next_payment': subscription.next_payment_date,  
            'plan_price': subscription.plan.price,
            'trial_days_left': days_left  
        }

        # Render the subscription settings page
        return render(request, 'submit/subscription_settings.html', context)

    except Subscription.DoesNotExist:
        # Handle case where the user doesn't have a subscription
        messages.warning(request, "You don't have an active subscription, Choose a plan here.")
        return redirect('subscription_plans')

    except Subscription.DoesNotExist:
        # Handle case where the user doesn't have a subscription
        messages.warning(request, "You don't have an active subscription.")
        return redirect('subscription_plans')


def subscription_success(request):
    return render(request, 'submit/subscription_success.html')

def subscription_failed(request):
    return render(request, 'submit/subscription_failed.html')


@require_POST
def register_free_plan(request, plan_id):
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, price=0)
        
        
        existing_subscription = Subscription.objects.filter(
            user=request.user,
            status='active'
        ).first()
        
        if existing_subscription:
            return JsonResponse({
                'success': False,
                'message': 'You already have an active subscription.'
            })

        
        subscription = Subscription.objects.create(
            user=request.user,
            plan=plan,
            status='active',
            created_at=timezone.now(),
            next_payment_date=timezone.now() + timezone.timedelta(days=30)  
        )

        
        ProductPeriod.objects.create(
            profile=request.user.profile,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            product_count=0
        )

        return JsonResponse({
            'success': True,
            'message': 'Free plan activated successfully'
        })

    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Invalid plan selected'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@require_POST
def cancel_plan(request):
    try:
        
        subscription = Subscription.objects.filter(
            user=request.user,
            status='active'
        ).first()
        
        if not subscription:
            return JsonResponse({
                'success': False,
                'message': 'No active subscription found.'
            })

        
        product_period = ProductPeriod.objects.filter(
            profile=request.user.profile,
            end_date__gt=timezone.now()
        ).first()

        
        subscription.delete()

        
        if product_period:
            product_period.delete()

        return JsonResponse({
            'success': True,
            'message': 'Subscription cancelled successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })