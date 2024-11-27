# emails/forms.py

# email_sender/forms.py
from django import forms
from .models import EmailTemplate

class EmailForm(forms.Form):
    recipient = forms.EmailField()
    template = forms.ModelChoiceField(queryset=EmailTemplate.objects.all())
