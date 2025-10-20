from django import forms
from .models import EmailCampaign, CustomerEmail, CampaignImage

class EmailCampaignForm(forms.ModelForm):
    class Meta:
        model = EmailCampaign
        fields = ['name', 'template', 'scheduled_for']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter campaign name'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_for': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

class CustomerEmailForm(forms.ModelForm):
    class Meta:
        model = CustomerEmail
        fields = ['email', 'customer_name']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'customer@example.com'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer Name (optional)'}),
        }

class CampaignImageForm(forms.ModelForm):
    class Meta:
        model = CampaignImage
        fields = ['image', 'alt_text']
        widgets = {
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'alt_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Describe this image'}),
        }

class AIEditForm(forms.Form):
    prompt = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'E.g., "Make this more festive for Christmas" or "Add a summer theme with beach imagery"',
            'rows': 4
        }),
        help_text="Describe how you want to modify the email content"
    )