from django.urls import path
from django.contrib.auth import views as auth_views
from submit import views as user_views
from .views import register
from submit import views
from .views import *

urlpatterns = [
    path('register/', register, name='register'),
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/',
         reset_password_view,
         name='reset_password'),
    path('logout/', logout_view, name='logout'),
    path('settings/', user_views.profile, name='profile'),
]
