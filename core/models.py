from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import models
import random
import datetime
from submit.models import Profile, CustomUser


class Category(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('contact', kwargs={'pk': self.pk})


class Product(models.Model):
    barcode = models.CharField(max_length=100, unique=True, default='12345')
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=10,
                              choices=[('IN', 'In Stock'),
                                       ('OUT', 'Out of Stock')],
                              default='IN')
    price = models.DecimalField(max_digits=10,
                                decimal_places=2,
                                default='12345')
    cost = models.DecimalField(max_digits=10,
                               decimal_places=2,
                               default='12345')
    category = models.ForeignKey(Category,
                                 on_delete=models.SET_NULL,
                                 null=True,
                                 blank=True)
    last_modified = models.DateTimeField(auto_now=True)
    date_added = models.DateTimeField(default=timezone.now)
    quantity = models.IntegerField(default=0)
    original_quantity = models.IntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profile = models.ForeignKey(Profile,
                                on_delete=models.CASCADE,
                                null=True,
                                blank=True)
    user = models.ForeignKey(CustomUser,
                             on_delete=models.CASCADE,
                             null=True,
                             blank=True)

    def __str__(self):
        return f"{self.name} ({self.barcode}) - {self.status}"

    def save(self, *args, **kwargs):
        if not self.id:  
            self.unit_price = self.price / self.quantity if self.quantity else 0
        super().save(*args, **kwargs)

    @property
    def total_price(self):
        return self.price * self.quantity

    @property
    def total_cost(self):
        return self.cost * self.quantity

    def calculate_profit_loss(self):
        profit_loss = self.price - self.cost
        if profit_loss > 0:
            return f"Profit: {profit_loss}"
        elif profit_loss < 0:
            return f"Loss: {-profit_loss}"
        else:
            return "No Profit No Loss"

    def update_status(self, new_status):

        self.status = new_status
        if new_status == 'OUT':
            self.last_modified = timezone.now()
        else:
            self.last_modified = None
        self.save()


class Sale(models.Model):
    transaction_id = models.CharField(max_length=50, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Sale {self.transaction_id}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)  
    product_barcode = models.CharField(max_length=100)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Transaction(models.Model):
    ACTION_CHOICES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
    ]

    product = models.ForeignKey('Product', on_delete=models.PROTECT)
    quantity = models.IntegerField()
    action = models.CharField(max_length=3, choices=ACTION_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    last_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.action} - {self.product.name} - Qty: {self.quantity}"

    class Meta:
        ordering = ['-last_modified']



class IncomeStatement(models.Model):
    sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_of_sales = models.DecimalField(max_digits=12,
                                        decimal_places=2,
                                        default=0)
    rent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    utilities = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salaries = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    marketing = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_income = models.DecimalField(max_digits=12,
                                       decimal_places=2,
                                       default=0)
    other_expenses = models.DecimalField(max_digits=12,
                                         decimal_places=2,
                                         default=0)
    interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dividends = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    profile = models.ForeignKey(Profile,
                                on_delete=models.CASCADE,
                                null=True,
                                blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def gross_profit(self):
        return self.sales - self.cost_of_sales

    def operating_expenses(self):
        return self.rent + self.utilities + self.salaries + self.marketing + self.insurance + self.other_expenses

    def operating_income(self):
        return self.gross_profit() - self.operating_expenses()

    def ebit(self):
        
        return self.operating_income() - self.interest

    def net_profit(self):
        
        return self.ebit() - self.tax - self.dividends

    def __str__(self):
        return f"Income Statement on {self.created_at.strftime('%Y-%m-%d')}"



class Barcode(models.Model):
    code = models.CharField(max_length=13, unique=True)
    product_name = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    @staticmethod
    def generate_unique_code(product_name, price):
        while True:
            code = ''.join([str(random.randint(0, 9)) for _ in range(12)])
            
            total = 0
            for i in range(12):
                if i % 2 == 0:
                    total += int(code[i])
                else:
                    total += int(code[i]) * 3
            check_digit = (10 - (total % 10)) % 10
            
            full_code = code + str(check_digit)
            
            if not Barcode.objects.filter(code=full_code).exists():
                return full_code, product_name, price


class EmailTemplate(models.Model):
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    filename = models.CharField(max_length=100, default='default_template.html') 

    def __str__(self):
        return self.name

class SentEmail(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email to {self.recipient} at {self.sent_at}"






class POSProduct(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE,null=True, blank=True )  # Changed from profile to user

    def __str__(self):
        return self.name

class POSTransaction(models.Model):
    order_number = models.CharField(max_length=4)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    money_rendered = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    change = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    collected = models.BooleanField(default=False)
    collected_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True )  

    class Meta:
        unique_together = ['order_number', 'user']  # Ensure order numbers are unique per user

    def save(self, *args, **kwargs):
        if not self.order_number:
            while True:
                number = str(random.randint(1000, 9999))
                if not POSTransaction.objects.filter(
                    order_number=number, 
                    user=self.user
                ).exists():
                    self.order_number = number
                    break
        super().save(*args, **kwargs)

    def mark_as_collected(self):
        self.collected = True
        self.collected_at = timezone.now()
        self.save()

class POSTransactionItem(models.Model):
    transaction = models.ForeignKey(POSTransaction, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(POSProduct, on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    product_name = models.CharField(max_length=255, blank=True)  # Add this field
    
    def save(self, *args, **kwargs):
        if not self.product_name:
            if self.product:
                self.product_name = self.product.name
            elif hasattr(self, '_inventory_product_name'):
                self.product_name = self._inventory_product_name
        super().save(*args, **kwargs)


class SalesForecast(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    forecast_date = models.DateTimeField(auto_now_add=True)
    forecast_data = models.TextField(default="nothing")
    situational_factors = models.TextField(default="nothing")

    def __str__(self):
        return f"Forecast for {self.user.username} on {self.forecast_date}"