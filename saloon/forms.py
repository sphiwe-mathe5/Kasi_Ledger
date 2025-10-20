# salon/forms.py
from django import forms
from .models import Worker, Style, StyleTicket
from core.models import CustomUser

class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = ['name', 'surname', 'phone', 'email', 'user']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'surname': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'user': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ✅ Fix: protect against NoneType user
        if self.instance and self.instance.pk and self.instance.user:
            # allow unassigned users + the one linked to this worker
            self.fields['user'].queryset = (
                CustomUser.objects.filter(worker_user__isnull=True) |
                CustomUser.objects.filter(pk=self.instance.user.pk)
            )
        else:
            # only allow unassigned users
            self.fields['user'].queryset = CustomUser.objects.filter(worker_user__isnull=True)

class StyleForm(forms.ModelForm):
    class Meta:
        model = Style
        fields = ['name', 'price', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),

        }

class StyleTicketForm(forms.ModelForm):
    class Meta:
        model = StyleTicket
        fields = ['customer_name', 'customer_phone', 'customer_email', 'style', 'worker']
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'customer_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'customer_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'style': forms.Select(attrs={'class': 'form-control'}),
            'worker': forms.Select(attrs={'class': 'form-control'}),
        }