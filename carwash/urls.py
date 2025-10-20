from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [

    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Employee URLs
    path('employees/', views.employee_list_create, name='employee_list_create'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/edit/', views.employee_update_delete, name='employee_update_delete'),
    
    # Service URLs
    path('services/', views.service_list_create, name='service_list_create'),
    path('services/<int:pk>/edit/', views.service_update_delete, name='service_update_delete'),
    
    # Ticket URLs
    path('tickets/', views.ticket_list_create, name='ticket_list_create'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/edit/', views.ticket_update_delete, name='ticket_update_delete'),
    #path('tickets/<int:pk>/quick-status/', views.quick_ticket_status_update, name='quick_ticket_status_update'),
    
    # Reports
    path('reports/revenue/', views.revenue_report, name='revenue_report'),
    
    # API endpoints
    path('carwash-ai-chat/', views.carwash_ai_chat_endpoint, name='carwash_ai_chat'),
    #path('api/service-price/', views.get_service_price, name='get_service_price'),
    path('get-customer-email/', views.get_customer_email, name='get_customer_email'),
    #path('employees/<int:pk>/update/', views.employee_update, name='employee_update'),
    
    # Service URLs
    #path('services/', views.service_list, name='service_list'),
    #path('services/create/', views.service_create, name='service_create'),
    #path('services/<int:pk>/update/', views.service_update, name='service_update'),
    
    # Ticket URLs
   # path('tickets/', views.ticket_list, name='ticket_list'),
    #path('tickets/create/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    #path('tickets/<int:pk>/update/', views.ticket_update, name='ticket_update'),
    
    # Reports
    path('reports/revenue/', views.revenue_report, name='revenue_report'),
]