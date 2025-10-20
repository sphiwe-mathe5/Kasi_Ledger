from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from core.models import Profile, CustomUser

class Employee(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="employee_user")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees_created")

    def __str__(self):
        return f"{self.name} {self.surname}"

    @property
    def full_name(self):
        return f"{self.name} {self.surname}"

    class Meta:
        ordering = ['name', 'surname']

class Service(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="service_user")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="services_created")

    def __str__(self):
        return f"{self.name} - R{self.price}"

    class Meta:
        ordering = ['name']

class ServiceTicket(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    car_number_plate = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True, null=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='tickets')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='tickets')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="tickets_user")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets_created")

    def save(self, *args, **kwargs):
        # Generate ticket number if not exists
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        
        # Set total amount from service price
        if self.service:
            self.total_amount = self.service.price
        
        # Set completed_at when status changes to completed
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)

    def generate_ticket_number(self):
        from datetime import datetime
        today = datetime.now().strftime('%Y%m%d')
        last_ticket = ServiceTicket.objects.filter(
            ticket_number__startswith=f'CW{today}'
        ).order_by('-ticket_number').first()
        
        if last_ticket:
            last_number = int(last_ticket.ticket_number[-3:])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'CW{today}{new_number:03d}'

    def __str__(self):
        return f"{self.ticket_number} - {self.car_number_plate}"

    class Meta:
        ordering = ['-created_at']