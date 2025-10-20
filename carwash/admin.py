from django.contrib import admin
from .models import Employee, Service, ServiceTicket

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'surname', 'email', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'surname', 'email']
    list_editable = ['is_active']

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    list_editable = ['price', 'is_active']

@admin.register(ServiceTicket)
class ServiceTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'car_number_plate', 'service', 'employee', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at', 'service', 'employee']
    search_fields = ['ticket_number', 'car_number_plate', 'customer_email']
    readonly_fields = ['ticket_number', 'total_amount']
    list_editable = ['status']