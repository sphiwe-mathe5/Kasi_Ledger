# salon/urls.py
from django.urls import path
from . import views

app_name = 'saloon'

urlpatterns = [
    path('saloon/', views.saloon, name='saloon'),
    path('workers/', views.worker_list_create, name='worker_list_create'),
    path('workers/<int:pk>/update/', views.worker_update, name='worker_update'),
    path('workers/<int:pk>/delete/', views.worker_delete, name='worker_delete'),
    path('styles/', views.style_list, name='style_list'),
    path('styles/add/', views.style_create, name='style_create'),
    path('styles/<int:pk>/edit/', views.style_edit, name='style_edit'),
    #path('tickets/', views.ticket_list, name='ticket_list'),
    path('salon-tickets/', views.ticket_create, name='ticket_create'),
    path('revenue/', views.salon_report, name='salon_report'),

    path('salon-ai-chat/', views.salon_ai_chat_endpoint, name='salon_ai_chat'),

    path('get-customer-emails/', views.get_customer_emails, name='get_customer_emails'),
    
    path('profile/setup/', views.create_salon_profile, name='create_salon_profile'),
    path('salon/<slug:slug>/', views.salon_profile, name='salon_profile'),
    path('salon/<slug:slug>/book/', views.create_booking, name='create_booking'),
    path('booking/<int:booking_id>/update/', views.update_booking_status, name='update_booking_status'),

    path('bookings/', views.manage_availability, name='manage_availability'),
    path('availability/slot/create/', views.create_availability_slot, name='create_availability_slot'),
    path('availability/recurring/create/', views.create_recurring_availability, name='create_recurring_availability'),
    path('availability/slot/<int:slot_id>/delete/', views.delete_availability_slot, name='delete_availability_slot'),
    
    
    # Public API for customers
    path('<slug:slug>/available-slots/', views.get_available_slots, name='get_available_slots'),
]