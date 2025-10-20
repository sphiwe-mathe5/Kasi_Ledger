from django.urls import path
from . import views

app_name = 'email_campaigns'

urlpatterns = [
    path('email-campaigns/', views.emails, name='emails'),

]