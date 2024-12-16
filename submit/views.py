from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.models import User
from .forms import SearchForm
from .models import Profile
from django.utils import timezone
import json
from decimal import Decimal
from submit.models import SubscriptionPlan, Subscription
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
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

            messages.success(request, 'Signup successful!')
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
            print("Authentication successful")  
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('index')
        else:
            print("Authentication failed")  
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
    messages.success(request, 'You have been logged out.')
    return redirect('index')


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Your account has been created! You are now able to log in')
            return redirect('index')
    else:
        form = UserRegisterForm()
    return render(request, 'submit/register.html', {'form': form})

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

@login_required
def initialize_payment(request, plan_id):
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
        
        
        amount_in_kobo = int(plan.price * 100)
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "email": request.user.email,
            "amount": amount_in_kobo,
            "currency": "ZAR",
            "callback_url": f"{settings.SITE_URL}/payment/callback/",
            "metadata": {
                "plan_id": plan_id,
                "user_id": request.user.id
            }
        }
        
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        return JsonResponse({"error": "Failed to initialize payment"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@login_required
def payment_callback(request):
    reference = request.GET.get('reference')
    if reference:
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }
        
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data['data']['status'] == 'success':
                
                metadata = response_data['data']['metadata']
                plan_id = metadata.get('plan_id')
                
                
                subscription, created = Subscription.objects.get_or_create(
                    user=request.user,
                    defaults={'plan_id': plan_id}
                )
                
                subscription.active = True
                subscription.paystack_reference = reference
                subscription.plan_id = plan_id
                subscription.next_payment_date = timezone.now() + timezone.timedelta(days=30)
                subscription.save()
                
                return redirect('subscription_success')
    
    return redirect('subscription_failed')

def subscription_success(request):
    return render(request, 'submit/subscription_success.html')

def subscription_failed(request):
    return render(request, 'submit/subscription_failed.html')