from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import Profile, CustomUser, PRICING_CHOICES
from django import forms



class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()
    pricing_plan = forms.ChoiceField(choices=PRICING_CHOICES)
    company_name = forms.CharField(max_length=100, required=False)

    class Meta:
        model = CustomUser
        fields = ['email', 'password1', 'password2', 'pricing_plan', 'company_name']  # Removed username


    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) < 8:
            raise ValidationError(
                "Password must be at least 8 characters long.")
        return password1

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error('password2', "The two password fields must match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.company_name = self.cleaned_data['company_name']
        if commit:
            user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    'pricing_plan': self.cleaned_data['pricing_plan'],
                }
            )
        return user

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()
    company_name = forms.CharField()

    class Meta:
        model = User
        fields = ['email', 'company_name']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['pricing_plan']


class SearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100)

