from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import models
from submit.models import Profile, CustomUser


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
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
        if not self.id:  # Only on creation
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
    cost_of_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    utilities = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salaries = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    marketing = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dividends = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def gross_profit(self):
        return self.sales - self.cost_of_sales

    def operating_expenses(self):
        return self.rent + self.utilities + self.salaries + self.marketing + self.insurance + self.other_expenses

    def operating_income(self):
        return self.gross_profit() - self.operating_expenses()

    def ebit(self):
        # EBIT: Earnings Before Interest and Taxes
        return self.operating_income() - self.interest

    def net_profit(self):
        # Net Profit = EBIT - Taxes - Dividends
        return self.ebit() - self.tax - self.dividends

    def __str__(self):
        return f"Income Statement on {self.created_at.strftime('%Y-%m-%d')}"




#<a href="https://www.freepik.com/search">Icon by pojok d</a>  <a href="https://www.freepik.com/search">Icon by Nuaba</a> <a href="https://www.freepik.com/search">Icon by Freepik</a><a href="https://www.freepik.com/search">Icon by Dewi Sari</a>
