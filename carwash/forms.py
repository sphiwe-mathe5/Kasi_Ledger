from django import forms
from .models import Employee, Service, ServiceTicket

class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['name', 'surname', 'phone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name'
            }),
            'surname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter surname'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and self.user:
            # Check if email already exists for the same user
            existing = Employee.objects.filter(
                email=email, 
                created_by=self.user
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("An employee with this email already exists.")
        return email

    def save(self, commit=True):
        employee = super().save(commit=False)
        if self.user:
            employee.created_by = self.user
        if commit:
            employee.save()
        return employee

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'price']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Full Wash, Bakkie Wash'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter price in Rands',
                'step': '0.01',
                'min': '0'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price and price <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return price

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and self.user:
            # Check if service name already exists for the same user
            existing = Service.objects.filter(
                name__iexact=name, 
                created_by=self.user
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("A service with this name already exists.")
        return name

    def save(self, commit=True):
        service = super().save(commit=False)
        if self.user:
            service.created_by = self.user
        if commit:
            service.save()
        return service

class ServiceTicketForm(forms.ModelForm):
    class Meta:
        model = ServiceTicket
        fields = ['car_number_plate', 'customer_email', 'service', 'employee']
        widgets = {
            'car_number_plate': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter car number plate',
                'style': 'text-transform: uppercase;'
            }),
            'customer_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Customer email (optional)'
            }),
            'service': forms.Select(attrs={
                'class': 'form-control'
            }),
            'employee': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        # Extract user before calling super()
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Only show active employees and services for the current user
        if self.user:
            self.fields['employee'].queryset = Employee.objects.filter(
                is_active=True, 
                created_by=self.user
            )
            self.fields['service'].queryset = Service.objects.filter(
                is_active=True, 
                created_by=self.user
            )
        else:
            # Fallback if no user provided
            self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
            self.fields['service'].queryset = Service.objects.filter(is_active=True)
        
        # Add empty labels
        self.fields['service'].empty_label = "Select a service"
        self.fields['employee'].empty_label = "Select an employee"

    def clean_car_number_plate(self):
        plate = self.cleaned_data.get('car_number_plate')
        if plate:
            return plate.upper().strip()
        return plate

class ServiceTicketUpdateForm(forms.ModelForm):
    class Meta:
        model = ServiceTicket
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }