from django.contrib import admin
from core.models import Product, IncomeStatement, Category, POSProduct

admin.site.register(Product)
admin.site.register(IncomeStatement)
admin.site.register(Category)
admin.site.register(POSProduct)
