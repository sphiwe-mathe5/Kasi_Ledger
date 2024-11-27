from django import forms
from .models import Product, Category
from .models import IncomeStatement

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True




class IncomeStatementForm(forms.ModelForm):
    class Meta:
        model = IncomeStatement
        fields = ['sales', 'cost_of_sales', 'rent', 'utilities', 'salaries', 'marketing', 
                  'insurance', 'other_income', 'other_expenses', 'interest', 'tax', 'dividends']
        widgets = {
            'sales': forms.NumberInput(attrs={'step': '0.01'}),
            'cost_of_sales': forms.NumberInput(attrs={'step': '0.01'}),
            'rent': forms.NumberInput(attrs={'step': '0.01'}),
            'utilities': forms.NumberInput(attrs={'step': '0.01'}),
            'salaries': forms.NumberInput(attrs={'step': '0.01'}),
            'marketing': forms.NumberInput(attrs={'step': '0.01'}),
            'insurance': forms.NumberInput(attrs={'step': '0.01'}),
            'other_income': forms.NumberInput(attrs={'step': '0.01'}),
            'other_expenses': forms.NumberInput(attrs={'step': '0.01'}),
            'interest': forms.NumberInput(attrs={'step': '0.01'}),
            'tax': forms.NumberInput(attrs={'step': '0.01'}),
            'dividends': forms.NumberInput(attrs={'step': '0.01'}),
        }
