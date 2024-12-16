from django.urls import path
from django.contrib.auth import views as auth_views
from submit import views as user_views
from .views import register
from submit import views
from .views import *

urlpatterns = [
    path('register/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/',reset_password_view,name='reset_password'),
    path('logout/', logout_view, name='logout'),
    path('settings/', user_views.profile, name='profile'),
    path('plans/', views.subscription_plans, name='subscription_plans'),
    path('subscribe/<int:plan_id>/', views.initialize_payment, name='initialize_payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/failed/', views.subscription_failed, name='subscription_failed'),
    path('forgot-admin-password/', views.forgot_admin_password_view, name='forgot_admin_password'),
    path('reset-admin-password/<str:token>/', views.reset_admin_password_view, name='reset_admin_password'),
]

