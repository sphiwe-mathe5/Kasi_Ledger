from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sub(value, arg):
    try:
        return Decimal(value) - Decimal(arg)
    except:
        return 0
    

@register.filter
def profit_loss(price, cost):
    try:
        return float(price) - float(cost)
    except:
        return 0
    

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''
        
@register.filter
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
    