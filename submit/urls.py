from django.urls import path
from django.contrib.auth import views as auth_views
from submit import views as user_views
from submit import views
from .views import *

urlpatterns = [
    path('register/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/',reset_password_view,name='reset_password'),
    path('logout/', logout_view, name='logout'),
    path('settings/', user_views.profile, name='profile'),
    path('subscribe/free/<int:plan_id>/', register_free_plan, name='register_free_plan'),
    path('plans/', views.subscription_plans, name='subscription_plans'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('subscribe/<int:plan_id>/', views.initialize_payment, name='initialize_payment'),
    path('webhooks/paystack/', views.webhook, name='paystack_webhook'),
    path('subscription/', views.subscription_settings, name='subscription_settings'),
    path('subscription/activate/', views.activate_subscription, name='activate_subscription'),
    path('subscription/delete/', views.delete_subscription, name='delete_subscription'),
    path('cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('cancel-plan/', views.cancel_plan, name='cancel_plan'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/failed/', views.subscription_failed, name='subscription_failed'),
    path('forgot-admin-password/', views.forgot_admin_password_view, name='forgot_admin_password'),
    path('reset-admin-password/<str:token>/', views.reset_admin_password_view, name='reset_admin_password'),
]

