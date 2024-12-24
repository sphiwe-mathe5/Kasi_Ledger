from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.models import User
from .forms import SearchForm
from .models import Profile
from django.utils import timezone
import json
import datetime
import hmac
import hashlib
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from submit.models import SubscriptionPlan, Subscription, PaymentHistory
from django.conf import settings
import requests
from django.db.models import Q
from django.db import models
from .models import User
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.contrib.auth import authenticate, login
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser, PasswordResetRequest, AdminPasswordResetRequest
from django.utils.crypto import get_random_string




def signup_view(request):
    if request.method == 'POST':
        admin_password = request.POST['admin_password']
        company_name = request.POST['company_name']
        email = request.POST['email']
        password = request.POST['password']

        try:
            
            user = CustomUser.objects.create_user(
                username=email,
                email=email,
                admin_password=admin_password,
                company_name=company_name,
                password=password,
            )

            login(request, user, backend='submit.backends.EmailBackend')

            return redirect('index')
        
        except IntegrityError:
            messages.error(request, 'An account with this email already exists. Please log in or use a different email.')

            return redirect('signup')  

    return render(request, 'submit/register.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        print(f"Attempting to log in with email: {email}")  

        user = authenticate(request, username=email, password=password)
        if user is not None:  
            login(request, user)
            return redirect('index')
        else:  
            messages.error(request, 'Invalid credentials')
    return render(request, 'submit/login.html')

def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        user = CustomUser.objects.filter(email=email).first()

        if user:
            token = get_random_string(32)
            reset_request = PasswordResetRequest.objects.create(user=user, email=email, token=token)
            reset_request.send_reset_email()
            messages.success(request, 'Reset link sent to your email.')
        else:
            messages.error(request, 'Email not found.')

    return render(request, 'submit/login.html')


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

def logout_view(request):
    logout(request)

    return redirect('index')


@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST,
                                   request.FILES,
                                   instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'updated!')
            return redirect('profile')

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {'u_form': u_form, 'p_form': p_form}

    return render(request, 'submit/profile.html', context)

    



@login_required
def subscription_plans(request):
    plans = SubscriptionPlan.objects.all()
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

        # Verify webhook signature
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
                # Get customer email from the payload
                customer_email = data.get('customer', {}).get('email')
                
                # Find the user by email
                try:
                    user = CustomUser.objects.get(email=customer_email)
                except CustomUser.DoesNotExist:
                    print(f"User not found for email: {customer_email}")
                    return HttpResponse(status=400)

                # Get the plan details
                plan_data = data.get('plan', {})
                try:
                    plan = SubscriptionPlan.objects.get(paystack_plan_code=plan_data.get('plan_code'))
                except SubscriptionPlan.DoesNotExist:
                    print(f"Plan not found for code: {plan_data.get('plan_code')}")
                    return HttpResponse(status=400)

                # Create or update subscription
                subscription = Subscription.objects.get_or_create(
                    user=user,
                    defaults={'plan': plan}
                )[0]

                # Update subscription details
                subscription.status = 'active'
                subscription.paystack_subscription_code = data.get('subscription_code')
                subscription.paystack_email_token = data.get('email_token')
                
                # Convert next_payment_date string to datetime
                next_payment_str = data.get('next_payment_date')
                if next_payment_str:
                    # Parse the ISO format datetime string and make it timezone-aware
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
            
            
            send_payment_success_email.delay(subscription.id)
            
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.error(f"Error processing successful charge: {str(e)}")
            return HttpResponse(status=500)

from django.db import transaction 
 
def payment_callback(request):
    reference = request.GET.get('reference')
    trxref = request.GET.get('trxref')
    
    # Log the callback
    print(f"Payment callback received - Reference: {reference}")
    
    # Verify the payment status
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


@login_required
def subscription_settings(request):
    try:
        subscription = Subscription.objects.get(user=request.user)
        payment_history = PaymentHistory.objects.filter(
            subscription=subscription
        ).order_by('-paid_at')
        
        context = {
            'subscription': subscription,
            'payment_history': payment_history,
            'current_plan': subscription.plan.name,
            'status': subscription.status,
            'next_payment': subscription.next_payment_date
        }
        return render(request, 'submit/subscription_settings.html', context)
    except Subscription.DoesNotExist:
        messages.warning(request, "You don't have an active subscription.")
        return redirect('subscription_plans')

def subscription_success(request):
    return render(request, 'submit/subscription_success.html')

def subscription_failed(request):
    return render(request, 'submit/subscription_failed.html')