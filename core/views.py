from collections import defaultdict
import decimal
from django.utils import timezone
import json
import random
from django.template.loader import render_to_string
import logging
from django.db import transaction
import datetime
from datetime import datetime, timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.mail import send_mail
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.hashers import check_password, make_password
from django.contrib import messages
from django.db.models.functions import TruncMonth, TruncDate
from core.forms import CategoryForm, SalesForecastForm
from .models import Product, Category, Transaction, EmailTemplate, SentEmail, StockImage
from submit.models import Profile, Subscription, SubscriptionPlan, ProductPeriod
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import io
import openai
import barcode  
from django.views.decorators.http import require_GET
from barcode.writer import ImageWriter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO
from django.db.models import Q, F
from .models import IncomeStatement, POSProduct, POSTransactionItem, POSTransaction
from .forms import IncomeStatementForm
from django.db.models import Count, Sum
from django.views.decorators.csrf import csrf_exempt
from .models import Product, Sale, SaleItem, Barcode
from decimal import Decimal, InvalidOperation
from django.db.models.functions import ExtractMonth
from django.urls import reverse, reverse_lazy
import random
from django.db.models import Q
from barcode.writer import ImageWriter
from io import BytesIO
import zipfile
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import tempfile
import os
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_GET
import datetime
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib import messages
from .forms import EmailForm
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
import requests
from rest_framework import viewsets
from .models import Product
from .serializers import ProductSerializer
from django.db.models import Sum
from saloon.views import get_salon_business_data
from saloon.models import StyleTicket
from saloon.subscriptions import check_feature_access
from saloon.decorators import company_category_required

from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)


def index(request):

    return render(request, 'core/index.html', {
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
    })
    
def law(request):

    return render(request, 'core/law.html')

@login_required
def console(request):
    """Console view with AI chat"""
    
    # Check subscription for AI chatbot access
    chatbot_access = check_feature_access(request.user, 'chatbot')
    
    # Get business data for both display and AI
    business_data = get_business_data(request.user)
    
    context = {
        # Basic metrics for dashboard
        'total_products': business_data['total_products'],
        'in_stock_products': business_data['in_stock_count'],
        'total_inventory_value': business_data['inventory_value'],
        'RECAPTCHA_PUBLIC_KEY': settings.RECAPTCHA_PUBLIC_KEY,
        
        # AI context - ALL the data for template
        'ai_context': {
            'business_name': business_data['business_name'],
            'total_products': business_data['total_products'],
            'in_stock_products': business_data['in_stock_count'],
            'out_of_stock_products': business_data['out_of_stock_count'],
            'critical_stock_count': business_data['critical_stock_count'],
            'low_stock_items_count': business_data['low_stock_count'],
            'total_inventory_value': business_data['inventory_value'],
            'potential_profit': business_data['potential_profit'],
            'total_actual_profit': business_data['profit_made'],
            'total_sales_revenue': business_data['total_revenue'],
            'total_products_sold': business_data['total_sold'],
        },
        
        # Critical alerts for immediate display
        'critical_alerts': {
            'has_critical_stock': business_data['critical_stock_count'] > 0,
            'has_low_stock': business_data['low_stock_count'] > 0,
            'has_alerts': business_data['critical_stock_count'] > 0 or business_data['low_stock_count'] > 0,
            'alert_count': business_data['critical_stock_count'] + business_data['low_stock_count'],
            'critical_items': business_data.get('critical_stock_items', []),
            'low_stock_items': business_data.get('low_stock_items_display', []),
        },
        
        # AI access control
        'ai_access': chatbot_access,
        'ai_ready': chatbot_access['allowed'],
    }
    
    return render(request, 'core/console.html', context)



class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('-date_added')
    serializer_class = ProductSerializer
    
@csrf_exempt
def subscribe(request):
    if request.method == 'POST':
        barcode = request.POST.get('barcode')
        action = request.POST.get('action', 'in')

        user = request.user
        try:
            profile = user.profile  
        except Profile.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User profile not found.'
            })

        # Check if the user has an active subscription or is within the trial period
        subscription = Subscription.objects.filter(user=user).first()

        if not subscription:
            return JsonResponse({
                'success': False,
                'message': 'Subscription not found.',
                'details': {
                    'type': 'no_subscription',
                    'title': 'Subscription Required',
                    'description': 'You need to subscribe to a plan to use this feature.',
                    'action_url': reverse('subscription_plans'),  
                    'action_text': 'View Plans'
                }
            })

        # Check if the user is within the trial period or has an active subscription
        if subscription.status == 'trialing' and subscription.trial_end_date > timezone.now():
            # Allow access during the trial period
            pass
        elif subscription.status == 'active':
            # Allow access for active subscriptions
            pass
        else:
            # Deny access if the trial has ended or the subscription is inactive
            return JsonResponse({
                'success': False,
                'message': 'Your free trial has ended.',
                'details': {
                    'type': 'trial_ended',
                    'title': 'Free Trial Ended',
                    'description': 'Your free trial has ended. To continue using this feature, please subscribe to a plan.',
                    'action_url': reverse('subscription_plans'),
                    'action_text': 'Subscribe Now'
                }
            })

        # Proceed with the scan-in or scan-out logic
        if action == 'in':
            existing_product = Product.objects.filter(barcode=barcode).first()
            if existing_product:
                return JsonResponse({
                    'success': False,
                    'message': 'Product with this barcode already exists. Use "Scan Out" to reduce quantity.'
                })

            name = request.POST.get('name')
            price = request.POST.get('price')
            cost = request.POST.get('cost')
            quantity = request.POST.get('quantity')
            category_id = request.POST.get('category')

            if not all([name, price, cost, quantity, category_id]):
                return JsonResponse({
                    'success': False,
                    'message': 'All product details including category and quantity are required for scan in.'
                })

            try:
                price = Decimal(price)
                cost = Decimal(cost)
                quantity = int(quantity)
                category = Category.objects.get(id=category_id)
            except (InvalidOperation, ValueError):
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid price, cost, or quantity value.'
                })
            except Category.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Selected category does not exist.'
                })

            # Create the product
            product = Product.objects.create(
                barcode=barcode,
                name=name,
                price=price,
                cost=cost,
                quantity=quantity,
                original_quantity=quantity,
                status='IN',
                category=category,
                profile=profile  
            )

            message = f'Product scanned in successfully. Quantity: {quantity}'
        else:  # action == 'out'
            try:
                product = Product.objects.get(barcode=barcode)
                if product.quantity > 0:
                    product.quantity -= 1
                    if product.quantity == 0:
                        product.status = 'OUT'
                    product.save()
                    message = f'Scanned out 1 unit. Remaining: {product.quantity}'
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Product is already out of stock'
                    })
            except Product.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Product not found. Please scan in the product first.'
                })

        return JsonResponse({
            'success': True,
            'message': message,
            'status': product.status,
            'name': product.name,
            'price': str(product.total_price),  
            'cost': str(product.total_cost),
            'quantity': product.quantity,
            'original_quantity': product.original_quantity,
            'category': product.category.name if product.category else ''
        })

    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
@company_category_required('restaurant', 'spaza')

def pos(request):
    products = Product.objects.filter(profile=request.user.profile)
    
    # Handle search query
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(barcode__icontains=search_query) | 
            Q(item_code__icontains=search_query)
        )
    
    context = {
        'products': products,
        'search_query': search_query,
    }
    return render(request, 'core/pos.html', context)



def check_product(request):
    barcode = request.GET.get('barcode')
    try:
        product = Product.objects.get(barcode=barcode, status='IN')
        return JsonResponse({
            'success': True,
            'product': {
                'name': product.name,
                'price': float(product.unit_price),
                'barcode': product.barcode,
                'quantity': product.quantity,
                'max_quantity': product.quantity,
            }
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Product not found'})



import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from decimal import Decimal
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from functools import wraps
import datetime

logger = logging.getLogger(__name__)

def send_receipt_email(email, receipt_data, request):
    """Send receipt email using system email (Gandi)"""
    user = request.user
    
    # Get company name from CustomUser model
    company_name = user.company_name or user.username or 'Our Store'

    # Render the HTML email template
    html_content = render_to_string('core/receipt_template.html', {
        'items': receipt_data['items'],
        'total': receipt_data['total'],
        'date': receipt_data['date'],
        'money_rendered': receipt_data['money_rendered'],
        'change': receipt_data['change'],
        'company_name': company_name,
        'user': {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'company_name': company_name
        }
    })
    
    # Create plain text version
    plain_text = f"""
Receipt from {company_name}

Date: {receipt_data['date']}
Seller: {receipt_data.get('seller', user.username)}

Items:
"""
    for item in receipt_data['items']:
        plain_text += f"- {item['name']} x {item['quantity']} @ R{item['price']:.2f} = R{item['total']:.2f}\n"
    
    plain_text += f"""
Total: R{receipt_data['total']:.2f}
Money Rendered: R{receipt_data['money_rendered']:.2f}
Change: R{receipt_data['change']:.2f}

Thank you for your purchase!
"""
    
    try:
        # Send using system email (Gandi) with proper from_email
        send_mail(
            subject=f'Receipt from {company_name}',
            message=plain_text,
            from_email=f"{company_name} <{settings.DEFAULT_FROM_EMAIL}>",  # ✅ Use system email
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        logger.info(f"✅ Receipt email sent successfully to {email}")
        print(f"✅ Receipt email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error sending receipt email to {email}: {str(e)}")
        print(f"❌ Error sending email: {str(e)}")
        return False


def require_profile(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'message': 'Authentication required'}, status=401)
        try:
            profile = request.user.profile
            request.profile = profile
            return view_func(request, *args, **kwargs)
        except Profile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Profile not found'}, status=403)
    return _wrapped_view


@csrf_exempt
@require_profile
def process_sale(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})

    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        customer_email = data.get('email')
        money_rendered = Decimal(str(data.get('money_rendered', '0')))
        
        with transaction.atomic():
            total = Decimal('0')
            product_details = []
            
            for item in items:
                barcode = item.get('barcode')
                item_code = item.get('item_code')
                
                # Try to find product by barcode or item_code
                try:
                    if barcode:
                        product = Product.objects.select_for_update().get(
                            barcode=barcode,
                            status='IN',
                            profile=request.profile
                        )
                    elif item_code:
                        product = Product.objects.select_for_update().get(
                            item_code=item_code,
                            status='IN',
                            profile=request.profile
                        )
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': 'Each item must have either a barcode or item_code'
                        })
                except Product.DoesNotExist:
                    identifier = barcode if barcode else item_code
                    return JsonResponse({
                        'success': False,
                        'message': f'Product with identifier {identifier} not found or does not belong to your profile'
                    })

                quantity = Decimal(str(item['quantity']))
                
                if product.quantity < quantity:
                    raise ValueError(f"Insufficient stock for product: {product.name}")
                
                # Use product.price (unit price) multiplied by quantity sold
                item_total = product.price * quantity
                total += item_total
                
                # ✅ NEW: Store customer email in the product when sold
                if customer_email:
                    product.customer_email = customer_email
                    product.sale_date = timezone.now()
                
                # Update product quantity and status
                product.quantity -= quantity
                product.status = 'OUT' if product.quantity == 0 else 'IN'
                product.save()

                Product.objects.filter(pk=product.pk).update(
                    quantity=product.quantity,
                    status=product.status
                )
                
                product_details.append({
                    'name': product.name,
                    'price': float(product.price),  # Unit price
                    'quantity': float(quantity),
                    'total': float(item_total),
                    'barcode': product.barcode,
                    'item_code': product.item_code
                })
            
            if money_rendered < total:
                raise ValueError("Insufficient money rendered")
                
            change = money_rendered - total

            receipt_data = {
                'items': product_details,
                'total': float(total),
                'money_rendered': float(money_rendered),
                'change': float(change),
                'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'seller': request.user.username
            }
            
            # Send receipt email if customer email provided
            email_sent = False
            if customer_email:
                try:
                    email_sent = send_receipt_email(
                        email=customer_email,
                        receipt_data=receipt_data,
                        request=request
                    )
                except Exception as e:
                    logger.error(f"Failed to send receipt email: {e}")
                    # Don't fail the sale if email fails
                    email_sent = False

            return JsonResponse({
                'success': True,
                'receipt_data': receipt_data,
                'email_sent': email_sent,
                'message': 'Sale processed successfully' + (' and receipt sent' if email_sent else ' but email failed')
            })

    except ValueError as e:
        logger.error(f"Validation error in sale: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
        
    except Exception as e:
        logger.error(f"Error processing sale: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'message': 'An error occurred processing your sale'}, status=500)



class PostCreateView(CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'core/unsubscribe.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        profile = Profile.objects.get(user=self.request.user)
        context['categories'] = Category.objects.filter(profile=profile)
        return context

    def form_valid(self, form):

        profile = Profile.objects.get(user=self.request.user)


        form.instance.profile = profile


        form.save()

        messages.success(self.request, 'Category created successfully!')
        return redirect('post-create')

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error creating the category.')
        return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):

        return reverse('contact')


@login_required
def create_income_statement(request):
    show_all = request.GET.get('show_all') == 'true'
    target_date = request.GET.get('date')
    out_of_stock_count = Product.objects.filter(status='OUT').count()

    categories = Category.objects.all()

    
    out_of_stock_per_month = Product.objects.filter(status='OUT').annotate(
        month=TruncMonth('date_added')
    ).values('month').annotate(count=Count('id')).order_by('month')

    products = Product.objects.annotate(
        month=TruncMonth('date_added'),
        date=TruncDate('date_added')).order_by('-date_added')

    grouped_products = defaultdict(lambda: defaultdict(list))
    monthly_totals = defaultdict(lambda: {'price': Decimal('0.00'), 'cost': Decimal('0.00'), 'profit_loss': Decimal('0.00')})

    for product in products:
        try:
            product.profit_loss = product.price - product.cost
            product.profit_loss_message = f"{product.profit_loss:.2f}"
        except Exception as e:
            print(f"Error calculating profit/loss for product {product.name}: {str(e)}")
            product.profit_loss_message = "Error calculating profit/loss"
            product.profit_loss = Decimal('0.00')

        grouped_products[product.month][product.date].append(product)

        
        monthly_totals[product.month]['price'] += product.price
        monthly_totals[product.month]['cost'] += product.cost
        monthly_totals[product.month]['profit_loss'] += product.profit_loss

    
    month_choices = [(month.strftime('%Y-%m'), month.strftime('%B %Y')) for month in monthly_totals.keys()]
    monthly_totals_json = {month.strftime('%Y-%m'): {
        'price': str(monthly_totals[month]['price']),
        'cost': str(monthly_totals[month]['cost']),
    } for month in monthly_totals.keys()}


    
    grouped_products_dict = {}
    for month, dates in grouped_products.items():
        grouped_products_dict[month] = {
            'dates': {},
            'monthly_total': monthly_totals[month]
        }
        for date, product_list in dates.items():
            date_str = date.strftime('%Y-%m-%d')
            if show_all and target_date and date_str == target_date:
                products_to_show = product_list
                show_all_flag = True
            else:
                products_to_show = product_list[:10]
                show_all_flag = False

            
            daily_total = {
                'price': sum(p.price for p in products_to_show),
                'cost': sum(p.cost for p in products_to_show),
                'profit_loss': sum(p.profit_loss for p in products_to_show)
            }

            grouped_products_dict[month]['dates'][date] = {
                'products': products_to_show,
                'total_count': len(product_list),
                'show_all': show_all_flag,
                'daily_total': daily_total
            }

    if request.method == 'POST':
        form = IncomeStatementForm(request.POST)
        if form.is_valid():
            income_statement = form.save(commit=False)  

            
            profile = Profile.objects.get(user=request.user)  
            income_statement.profile = profile  

            income_statement.save()  

            
            return redirect('view_income_statement', pk=income_statement.pk)
    else:
        form = IncomeStatementForm()

    
    context = {
        'form': form,
        'month_choices': month_choices,
        'monthly_totals': monthly_totals,
        'monthly_totals_json': json.dumps(monthly_totals_json),
    }

    return render(request, 'core/create_income_statement.html', context)


@login_required  
def view_income_statement(request, pk):
    statements = IncomeStatement.objects.filter(profile__user=request.user)  

    context = {
        'statements': statements,
    }

    return render(request, 'core/list_income_statements.html', context)




def unsubscribed(request):
    categories = Category.objects.all().order_by('name')
    categories_data = [{'id': category.id, 'name': category.name} for category in categories]
    return JsonResponse({'success': True, 'categories': categories_data})





@login_required
@company_category_required('restaurant', 'spaza')
def contact(request):
    user = request.user
    
    # Check if transactions are already unlocked in this session
    transactions_unlocked = request.session.get('transactions_unlocked', False)
    
    # Handle PIN verification
    if request.method == 'POST' and 'transaction_pin' in request.POST:
        entered_pin = request.POST.get('transaction_pin', '').strip()
        
        if not entered_pin:
            messages.error(request, "Please enter your PIN.")
        elif user.check_transaction_pin(entered_pin):
            request.session['transactions_unlocked'] = True
            messages.success(request, "Transactions unlocked successfully!")
            return redirect('contact')  # Redirect to clear POST data
        else:
            messages.error(request, "Incorrect PIN. Please try again.")

    show_all = request.GET.get('show_all') == 'true'
    target_date = request.GET.get('date')
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    
    profile = get_object_or_404(Profile, user=request.user)
    categories = Category.objects.filter(profile=profile)
    
    out_of_stock_count = Product.objects.filter(status='OUT', profile=profile).count()

    
    products = Product.objects.filter(profile=profile)

    needs_unlock = user.has_transaction_pin() and not transactions_unlocked

    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    if category_filter:
        products = products.filter(category__name=category_filter)
        
    if status_filter:
        products = products.filter(status=status_filter)

    
    products = products.annotate(
        month=TruncMonth('date_added'),
        date=TruncDate('date_added')
    ).order_by('-date_added')

    
    out_of_stock_per_month = Product.objects.filter(profile=profile, status='OUT').annotate(
        month=TruncMonth('date_added')
    ).values('month').annotate(count=Count('id')).order_by('month')

    grouped_products = defaultdict(lambda: defaultdict(list))
    monthly_totals = defaultdict(lambda: {'price': Decimal('0.00'), 'cost': Decimal('0.00'), 'profit_loss': Decimal('0.00')})

    
    for product in products:
        grouped_products[product.month][product.date].append(product)
        # Use the @property methods for totals
        monthly_totals[product.month]['price'] += product.total_price
        monthly_totals[product.month]['cost'] += product.total_cost
        monthly_totals[product.month]['profit_loss'] += product.profit_loss

    
    grouped_products_dict = {}
    
    for month, dates in grouped_products.items():
        grouped_products_dict[month] = {
            'dates': {},
            'monthly_total': monthly_totals[month]
        }
        
        for date, product_list in dates.items():
            date_str = date.strftime('%Y-%m-%d')
            if show_all and target_date and date_str == target_date:
                products_to_show = product_list
                show_all_flag = True
            else:
                products_to_show = product_list[:10]
                show_all_flag = False

            daily_total = {
                'price': sum(p.total_price for p in products_to_show),
                'cost': sum(p.total_cost for p in products_to_show),
                'profit_loss': sum(p.profit_loss for p in products_to_show)
            }

            grouped_products_dict[month]['dates'][date] = {
                'products': products_to_show,
                'total_count': len(product_list),
                'show_all': show_all_flag,
                'daily_total': daily_total
            }

    return render(request, 'core/contact.html', {
        'categories': categories,

        'grouped_products': grouped_products_dict,
        'out_of_stock_count': out_of_stock_count,
        'out_of_stock_per_month': out_of_stock_per_month,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'has_transaction_pin': user.has_transaction_pin(),
        'transactions_unlocked': transactions_unlocked,
        'needs_unlock': needs_unlock,
        'show_all': show_all,
    })

@login_required
def lock_transactions(request):
    """Lock transactions by clearing the session"""
    if 'transactions_unlocked' in request.session:
        del request.session['transactions_unlocked']
    messages.success(request, "Transactions locked successfully!")
    return redirect('contact')


@require_GET
def enquire(request):
    last_update = request.GET.get('last_update')

    if last_update:
        last_update = timezone.datetime.fromisoformat(last_update)
        updated_products = Product.objects.filter(last_modified__gt=last_update)
    else:
        updated_products = Product.objects.all()

    product_data = []
    for product in updated_products:
        product_data.append({
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode,
            'status': product.status,
            'category': str(product.category),
            'price': str(product.price),
            'cost': str(product.cost),
            'quantity': str(product.quantity),
            'original_quantity': str(product.original_quantity),
            'date_added': product.date_added.isoformat(),
            'last_modified': product.last_modified.isoformat(),
            'profit_loss_message': product.calculate_profit_loss(),
        })

    return JsonResponse({
        'products': product_data,
        'server_time': timezone.now().isoformat()
    })



def optout(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        username = request.POST.get('username')

        send_mail(
            subject='Post more inquiry',
            message=f'Email: {email}\nUsername: {username}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=False,
        )

        messages.success(
            request,
            'Your enquiry has been received, we will send you an email soon')
        return redirect('unsubscribe')

    return redirect('index')

@login_required
def list_income_statements(request):
    statements = IncomeStatement.objects.filter(profile__user=request.user)


    context = {
        'statements': statements,
    }
    return render(request, 'core/list_income_statements.html', context)


def guide(request):

    return render(request, 'core/guide.html')

def organize_products_by_date(products):
    """Helper function to organize products by date"""
    from collections import defaultdict
    organized = defaultdict(list)
    
    for product in products:
        month = product.date_added.strftime('%Y-%m')
        organized[month].append(product)
        
    return organized

@company_category_required('restaurant', 'spaza')
def inventory_view(request):
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    
    products = Product.objects.all()
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    if category_filter:
        products = products.filter(category=category_filter)
        
    if status_filter:
        products = products.filter(status=status_filter)
        
    
    categories = Product.objects.values_list('category', flat=True).distinct()
    
    
    month_data = organize_products_by_date(products)  
    
    context = {
        'month_data': month_data,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
    }
    return render(request, 'core/contact.html', context)

def generate_barcodes(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to download barcodes.")
            return render(request, 'core/generate_barcodes.html')

        try:
            subscription = Subscription.objects.get(user=request.user)
        except Subscription.DoesNotExist:
            messages.error(request, "You must have a subscription to download barcodes.")
            return render(request, 'core/generate_barcodes.html')

        # Check if the user is within the free trial period
        if subscription.status == 'trialing' and subscription.trial_end_date > timezone.now():
            # Allow barcode generation during the free trial
            pass
        else:
            # Deny barcode generation if the trial has ended or the user doesn't have a subscription
            messages.error(request, "This Feature requires an Enterprise plan. Please subscribe to a plan to generate barcodes.")
            return render(request, 'core/generate_barcodes.html')

        quantity = int(request.POST.get('quantity', 1))
        format_type = request.POST.get('format', 'pdf')

        generated_codes = []
        for i in range(1, quantity + 1):
            product_name = request.POST.get(f'product_name_{i}')
            price = request.POST.get(f'price_{i}')
            code, product_name, price = Barcode.generate_unique_code(product_name, price)
            Barcode.objects.create(code=code, product_name=product_name, price=price)
            generated_codes.append((code, product_name, price))

        if format_type == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="barcodes.pdf"'
            
            c = canvas.Canvas(response, pagesize=A4)
            width, height = A4
            
            x_start = 20 * mm
            y_start = height - 30 * mm
            barcode_height = 20 * mm  # Adjusted height for cleaner layout
            spacing = 30 * mm  # Consistent spacing between barcodes
            codes_per_page = 20  # Number of codes per page
            barcodes_per_row = 2  # Number of barcodes per row (adjust as needed)
            row_spacing = 45 * mm  # Vertical spacing between rows
            col_spacing = 70 * mm  # Horizontal spacing between barcodes in a row
            
            with tempfile.TemporaryDirectory() as temp_dir:
                for idx, (code, product_name, price) in enumerate(generated_codes):
                    if idx > 0 and idx % codes_per_page == 0:
                        c.showPage()  # Start a new page
                        y_start = height - 30 * mm  # Reset Y position
                    
                    row = (idx % codes_per_page) // barcodes_per_row  # Calculate which row the barcode is in
                    col = (idx % barcodes_per_row)  # Calculate which column the barcode is in
                    
                    ean = barcode.get('ean13', code, writer=ImageWriter())
                    temp_path = os.path.join(temp_dir, f'barcode_{code}.png')
                    
                    img_buffer = BytesIO()
                    ean.write(img_buffer)
                    
                    img_buffer.seek(0)
                    img = Image.open(img_buffer)
                    img.save(temp_path, 'PNG')
                    img_buffer.close()
                    
                    if os.path.exists(temp_path):
                        # Calculate position for the barcode and text
                        y_pos = y_start - (row * row_spacing)
                        x_pos = x_start + (col * col_spacing)
                        
                        try:
                            # Draw the barcode image
                            c.drawImage(temp_path, x_pos, y_pos, width=60*mm, height=barcode_height)
                            
                            # Draw product details below the barcode
                            c.setFont("Helvetica", 10)  # Smaller font for details
                            c.drawString(x_pos + 10*mm , y_pos - 5*mm, f"Company: {request.user.company_name}")
                            c.drawString(x_pos + 10*mm, y_pos - 10*mm, f"Product: {product_name}")
                            c.drawString(x_pos + 10*mm, y_pos - 15*mm, f"Price: R{price}")
                            c.drawString(x_pos + 10*mm, y_pos - 20*mm, f"Barcode: {code}")
                        except Exception as e:
                            print(f"Error drawing image: {e}")
                    else:
                        print(f"File not found: {temp_path}")
                
                c.save()
            
            return response
            
        else:  
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for code, product_name, price in generated_codes:
                    ean = barcode.get('ean13', code, writer=ImageWriter())
                    img_buffer = BytesIO()
                    ean.write(img_buffer)
                    
                    zip_file.writestr(f'barcode_{code}.png', img_buffer.getvalue())
                    
                    # Create a text file with product info
                    product_info = f"Product Name: {product_name}\nPrice: ${price}\nBarcode: {code}"
                    zip_file.writestr(f'barcode_{code}_info.txt', product_info)
                    
                    img_buffer.close()
            
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="barcodes.zip"'
            
            return response
    
    return render(request, 'core/generate_barcodes.html')


def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    messages.success(request, 'Product deleted successfully')
    return redirect('contact')


def is_admin(user):
    if not user.is_staff:
        raise PermissionDenied("You don't have permission to access this page.")
    return True

@user_passes_test(is_admin)
@login_required
def send_email(request):
    if request.method == 'POST':
        form = EmailForm(request.POST)
        if form.is_valid():
            recipients = form.cleaned_data['recipient']
            template = form.cleaned_data['template']
            
            
            recipient_list = [email.strip() for email in recipients.split(',')]

            
            html_message = render_to_string(f'emails/{template.filename}', {})

            
            send_mail(
                subject=template.subject,
                message='',  
                html_message=html_message,
                from_email='prettysweetmeassages_PSM@outlook.com',
                recipient_list=recipient_list,  
                fail_silently=False,
            )

            messages.success(request, 'Email sent successfully!')
            return redirect('send_email')
    else:
        form = EmailForm()

    return render(request, 'core/send_email.html', {'form': form})


def email(request):
    if request.method == 'POST':
        # Verify reCAPTCHA
        recaptcha_token = request.POST.get('recaptcha_token')
        data = {
            'secret': settings.RECAPTCHA_PRIVATE_KEY,
            'response': recaptcha_token
        }
        r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
        result = r.json()

        if not result.get('success', False) or result.get('score', 0) < 0.5:  # Adjust score threshold as needed
            messages.error(request, 'Verification failed. Please try again.')
            return redirect('index')

        email = request.POST.get('email')
        
        # Your existing email sending code
        email_message = EmailMessage(
            subject='New Subscription from',
            body=f'Email: {email}',
            from_email=settings.ADMIN_EMAIL,  
            to=[settings.ADMIN_EMAIL],
            reply_to=[email],  
        )
        email_message.send(fail_silently=False)

        html_content = render_to_string('core/subscribe.html', {'email': email})

        confirmation_email = EmailMultiAlternatives(
            subject="Subscription Confirmation", 
            body='', 
            from_email=settings.ADMIN_EMAIL,  
            to=[email],  
        )
        confirmation_email.attach_alternative(html_content, "text/html") 
        confirmation_email.send(fail_silently=False)

        messages.success(request)
        return redirect('index')

    return redirect('index')

@company_category_required('restaurant', 'spaza')
@login_required
def pos_view(request):
    products = POSProduct.objects.filter(user=request.user)
    items = Product.objects.filter(
        profile=request.user.profile,
        status='IN',
        quantity__gt=0
    )
    
    # Calculate price per unit for inventory products
    for item in items:
        item.price_per_unit = item.price / item.original_quantity if item.original_quantity else 0
    
    pending_orders = POSTransaction.objects.filter(
        user=request.user,
        collected=False
    ).order_by('created_at')
    
    return render(request, 'core/pos_view.html', {
        'products': products,
        'items': items,
        'pending_orders': pending_orders
    })


@login_required
@csrf_exempt
def add_product(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product = POSProduct.objects.create(
            name=data['name'],
            price=data['price'],
            user=request.user
        )
        return JsonResponse({
            'id': product.id,
            'name': product.name,
            'price': str(product.price)
        })

@login_required
@csrf_exempt
def complete_sale(request):
    if request.method == 'POST':
        try:
            # Check subscription status (keep your existing subscription checks)
            subscription = Subscription.objects.filter(user=request.user).first()
            if not subscription:
                return JsonResponse({
                    'success': False,
                    'message': 'Subscription required.',
                    'details': {
                        'type': 'no_subscription',
                        'title': 'Subscription Required',
                        'description': 'You need to subscribe to a plan to complete sales. Choose between our Free or Pro plans.',
                        'action_url': reverse('subscription_plans'),  
                        'action_text': 'View Plans'
                    }
                }, status=403)

            if subscription.status == 'trialing' and subscription.trial_end_date <= timezone.now():
                return JsonResponse({
                    'success': False,
                    'message': 'Your free trial has ended.',
                    'details': {
                        'type': 'trial_ended',
                        'title': 'Free Trial Ended',
                        'description': 'Your free trial has ended. To continue completing sales, please subscribe to a plan.',
                        'action_url': reverse('subscription_plans'),  
                        'action_text': 'Subscribe Now'
                    }
                }, status=403)

            data = json.loads(request.body)
            
            with transaction.atomic():
                # Create transaction
                pos_transaction = POSTransaction.objects.create(
                    total_amount=data['total_amount'],
                    money_rendered=data.get('money_rendered'),
                    change=data.get('change', 0),
                    user=request.user
                )

                product_details = []
                
                for item in data['items']:
                    if item.get('type') == 'inventory':
                        # Handle Inventory Products (with quantity deduction)
                        product = Product.objects.select_for_update().get(
                            id=item['product_id'],
                            profile=request.user.profile,
                            status='IN'
                        )
                        
                        # Verify and update quantity
                        if product.quantity < item['quantity']:
                            raise Exception(f'Not enough stock for {product.name}')
                        
                        product.quantity -= item['quantity']
                        if product.quantity <= 0:
                            product.status = 'OUT'
                        product.save()
                        
                        # Create transaction item without linking to POSProduct
                        POSTransactionItem.objects.create(
                            transaction=pos_transaction,
                            product=None,
                            quantity=item['quantity'],
                            price=item['price'],
                            product_name=product.name
                        )
                    else:
                        # Handle POS Products (no quantity tracking)
                        product = POSProduct.objects.get(
                            id=item['product_id'],
                            user=request.user
                        )
                        
                        # Create transaction item linked to POSProduct
                        POSTransactionItem.objects.create(
                            transaction=pos_transaction,
                            product=product,
                            quantity=item['quantity'],
                            price=item['price']
                        )
                    
                    product_details.append({
                        'name': item['name'],
                        'quantity': item['quantity'],
                        'price': item['price']
                    })

                return JsonResponse({
                    'success': True,
                    'new_pending_order': {
                        'id': pos_transaction.id,
                        'order_number': pos_transaction.order_number,
                        'total_amount': pos_transaction.total_amount,
                        'created_at': pos_transaction.created_at.isoformat(),
                        'products': product_details
                    },
                    'order_number': pos_transaction.order_number,
                    'total': str(pos_transaction.total_amount),
                    'change': str(pos_transaction.change)
                })

        except (POSProduct.DoesNotExist, Product.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@csrf_exempt
def mark_collected(request, order_id):
    transaction = get_object_or_404(POSTransaction, id=order_id, user=request.user)
    transaction.mark_as_collected()
    return JsonResponse({'status': 'success'})

@login_required
@company_category_required('restaurant', 'spaza')
def sales_analytics(request):
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=6)
    current_year = timezone.now().year
    current_month = timezone.now().month
    
    
    daily_sales = POSTransaction.objects.filter(
        user=request.user,
        created_at__date__range=[start_date, end_date]
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total_sales=Sum('total_amount'),
        orders_count=Count('id')
    ).order_by('date')

    monthly_sales = POSTransaction.objects.filter(
        user=request.user,
        created_at__year=current_year
    ).annotate(
        month=ExtractMonth('created_at')
    ).values('month').annotate(
        total_sales=Sum('total_amount'),
        orders_count=Count('id')
    ).order_by('month')
    
    
    months_data = []
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    
    for month_num in range(1, current_month + 1):
        month_data = next(
            (item for item in monthly_sales if item['month'] == month_num),
            {'month': month_num, 'total_sales': 0, 'orders_count': 0}
        )
        
        months_data.append({
            'name': month_names[month_num - 1],
            'total_sales': month_data['total_sales'],
            'orders_count': month_data['orders_count']
        })

    
    total_sales = POSTransaction.objects.filter(
        user=request.user,
        created_at__date__range=[start_date, end_date]
    ).aggregate(
        total_amount=Sum('total_amount'),
        total_orders=Count('id')
    )

    
    average_order = (
        total_sales['total_amount'] / total_sales['total_orders']
        if total_sales['total_orders'] > 0
        else 0
    )

    
    product_sales = POSTransactionItem.objects.filter(
        transaction__user=request.user,
        transaction__created_at__date__range=[start_date, end_date]
    ).values('product__name').annotate(
        total_quantity=Sum('quantity'),
        total_amount=Sum('price')
    ).order_by('-total_quantity')

    
    pending_orders = POSTransaction.objects.filter(
        user=request.user,
        collected=False
    ).order_by('created_at')

    
    order_history = POSTransaction.objects.select_related('user').prefetch_related(
        'items',
        'items__product'
    ).filter(
        user=request.user,
        collected=True  
    ).order_by('-created_at')

    
    print(f"Found {order_history.count()} orders in history")

    context = {
        'daily_sales': daily_sales,
        'product_sales': product_sales,
        'start_date': start_date,
        'end_date': end_date,
        'total_sales_amount': total_sales['total_amount'] or 0,
        'total_orders': total_sales['total_orders'] or 0,
        'average_order_value': average_order,
        'pending_orders': pending_orders,
        'order_history': order_history,
        'monthly_sales': months_data,
        'current_year': current_year,
    }
    
    return render(request, 'core/analytics.html', context)



#django rest framework viewsets for Product model
import base64, json, uuid
from django.db.models import F
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status
from .serializers import ProductSerializer, RecognizedItemSerializer, CommitItemsSerializer
from rest_framework.permissions import IsAuthenticated


logger = logging.getLogger(__name__)

def ai_stock_page(request):
    user = request.user
    
    # Check subscription for AI image recognition access
    image_recognition_access = check_feature_access(user, 'ai_image_recognition')
    
    # Get user's profile
    try:
        user_profile = user.profile
    except:
        user_profile = None

    search_query = request.GET.get("search", "")
    category_filter = request.GET.get("category", "")
    status_filter = request.GET.get("status", "")

    # Filter products by both user and profile
    products = Product.objects.filter(user=user)
    
    # If user has a profile, also filter by profile
    if user_profile:
        products = products.filter(profile=user_profile)

    # Filtering
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(item_code__icontains=search_query)
        )
    
    if category_filter:
        products = products.filter(category__name=category_filter)
    
    if status_filter:
        products = products.filter(status=status_filter)

    # Group by Month -> Date -> Products
    grouped_products = {}
    
    for product in products.order_by("-date_added"):
        # Get month key (first day of the month)
        month_key = product.date_added.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get date key (date only, no time)
        date_key = product.date_added.date()
        
        # Initialize month if not exists
        if month_key not in grouped_products:
            grouped_products[month_key] = {
                "dates": {},
                "monthly_total": {"price": 0, "cost": 0, "profit_loss": 0}
            }
        
        # Initialize date if not exists
        if date_key not in grouped_products[month_key]["dates"]:
            grouped_products[month_key]["dates"][date_key] = {
                "products": [],
                "daily_total": {"price": 0, "cost": 0, "profit_loss": 0},
                "total_count": 0
            }
        
        # Calculate profit/loss for this product
        try:
            product_profit_loss = (float(product.price) - float(product.cost)) * float(product.quantity)
        except:
            product_profit_loss = 0
        
        # Add product to date group
        grouped_products[month_key]["dates"][date_key]["products"].append(product)
        grouped_products[month_key]["dates"][date_key]["daily_total"]["price"] += float(product.price) * float(product.quantity)
        grouped_products[month_key]["dates"][date_key]["daily_total"]["cost"] += float(product.cost) * float(product.quantity)
        grouped_products[month_key]["dates"][date_key]["daily_total"]["profit_loss"] += product_profit_loss
        grouped_products[month_key]["dates"][date_key]["total_count"] += 1
        
        # Update monthly totals
        grouped_products[month_key]["monthly_total"]["price"] += float(product.price) * float(product.quantity)
        grouped_products[month_key]["monthly_total"]["cost"] += float(product.cost) * float(product.quantity)
        grouped_products[month_key]["monthly_total"]["profit_loss"] += product_profit_loss

    # Sort months in descending order (newest first)
    sorted_months = sorted(grouped_products.keys(), reverse=True)
    sorted_grouped_products = {month: grouped_products[month] for month in sorted_months}
    
    # For each month, sort dates in descending order
    for month, month_data in sorted_grouped_products.items():
        sorted_dates = sorted(month_data["dates"].keys(), reverse=True)
        month_data["dates"] = {date: month_data["dates"][date] for date in sorted_dates}

    # Get categories for the filter dropdown
    categories = []
    if user_profile:
        category_products = Product.objects.filter(user=user, profile=user_profile).exclude(category__isnull=True)
    else:
        category_products = Product.objects.filter(user=user).exclude(category__isnull=True)
    
    categories = category_products.values_list('category__name', flat=True).distinct()
    categories_list = [{'name': name} for name in categories if name]

    context = {
        "grouped_products": sorted_grouped_products.items(),
        "search_query": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "categories": categories_list,
        "total_products": products.count(),
        "image_recognition_access": image_recognition_access,
    }

    return render(request, "core/ai_stock.html", context)

AI_PROMPT = """
You are an inventory assistant. Extract items from the image and return STRICT JSON only:
{
  "items": [
    {"name": "...", "quantity": 1, "category": "..."},
    ...
  ]
}
Rules:
- "name": short market/common product name (brand + product if visible).
- "quantity": count visible units for that item (integer >= 1).
- "category": simple category (e.g., "Spices", "Sauces", "Seasoning"). If unsure, use "".
Return ONLY valid JSON. No explanations.
"""

def validate_and_process_image(image_file):
    """
    Validate image and return processed image data for OpenAI API
    """
    try:
        # Validate file size (max 20MB for OpenAI)
        max_size = 20 * 1024 * 1024  # 20MB
        if hasattr(image_file, 'size') and image_file.size > max_size:
            raise ValueError("Image file too large. Maximum size is 20MB.")

        # Read the original image data
        if hasattr(image_file, 'read'):
            image_file.seek(0)  # Reset file pointer
            image_data = image_file.read()
            image_file.seek(0)  # Reset again for potential reuse
        else:
            image_data = image_file

        # Validate it's a valid image using PIL
        try:
            img = Image.open(BytesIO(image_data))
            img.verify()
        except Exception as e:
            raise ValueError(f"Invalid image file: {str(e)}")

        # Check image format
        img = Image.open(BytesIO(image_data))
        if img.format not in ['JPEG', 'PNG', 'WEBP']:
            # Convert to JPEG if it's not in supported format
            if img.mode in ('RGBA', 'LA', 'P'):
                # Convert RGBA/LA/Palette to RGB
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Convert to JPEG
            output = BytesIO()
            img.save(output, format='JPEG', quality=90)
            image_data = output.getvalue()

        # Resize if too large (OpenAI recommends max 2048x2048)
        img = Image.open(BytesIO(image_data))
        max_dimension = 2048
        if img.width > max_dimension or img.height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            output = BytesIO()
            img.save(output, format='JPEG', quality=90)
            image_data = output.getvalue()

        return image_data

    except Exception as e:
        logger.error(f"Image validation/processing failed: {e}")
        raise ValueError(f"Image processing failed: {str(e)}")

def call_openai_vision_return_json(image_data: bytes) -> dict:
    """
    Calls OpenAI Chat Completions with image bytes and asks for JSON.
    Returns a Python dict like {"items": [...]}. On error, returns {"items": []}.
    """
    try:
        # Validate API key exists
        if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not configured")
            return {"items": [], "error": "OpenAI API key not configured"}

        # Encode image to base64
        b64_image = base64.b64encode(image_data).decode("utf-8")
        
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": AI_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}",
                                "detail": "high"
                            }
                        }
                    ],
                }
            ],
            "max_tokens": 1000,
        }
        
        logger.info(f"Calling OpenAI API for image recognition (image size: {len(image_data)} bytes)")
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions", 
            headers=headers, 
            json=payload, 
            timeout=120  # Increased timeout
        )
        
        # Log response details for debugging
        logger.info(f"OpenAI API response status: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"OpenAI API error response: {error_text}")
            return {"items": [], "error": f"OpenAI API error: {response.status_code}"}
        
        data = response.json()
        
        if "choices" not in data or len(data["choices"]) == 0:
            logger.error(f"Invalid OpenAI response structure: {data}")
            return {"items": [], "error": "Invalid response from OpenAI"}
        
        content = data["choices"][0]["message"]["content"]
        logger.info(f"OpenAI response content: {content}")
        
        # Parse the JSON response
        parsed = json.loads(content)
        
        if isinstance(parsed, dict) and "items" in parsed and isinstance(parsed["items"], list):
            # Normalize and validate items
            valid_items = []
            for item in parsed["items"]:
                try:
                    # Ensure required fields and types
                    normalized_item = {
                        "name": str(item.get("name", "")).strip(),
                        "quantity": max(int(item.get("quantity", 1)), 1),
                        "category": str(item.get("category", "")).strip()
                    }
                    
                    # Only include items with non-empty names
                    if normalized_item["name"]:
                        valid_items.append(normalized_item)
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping invalid item {item}: {e}")
                    continue
            
            logger.info(f"Successfully processed {len(valid_items)} items from OpenAI")
            return {"items": valid_items}
        else:
            logger.error(f"Invalid response format from OpenAI: {parsed}")
            return {"items": [], "error": "Invalid response format"}
            
    except requests.RequestException as e:
        logger.error(f"OpenAI API request failed: {e}")
        return {"items": [], "error": f"API request failed: {str(e)}"}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON response: {e}")
        return {"items": [], "error": "Failed to parse response"}
    except Exception as e:
        logger.error(f"Unexpected error in OpenAI call: {e}")
        return {"items": [], "error": f"Unexpected error: {str(e)}"}

class AIRecognizeAPIView(APIView):
    """
    POST multipart/form-data with 'image': returns {"items":[{name,quantity,category},...]}
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            # Check subscription access first
            from saloon.subscriptions import check_feature_access
            access_check = check_feature_access(request.user, 'ai_image_recognition')
            
            if not access_check['allowed']:
                return Response(
                    {
                        "detail": access_check['message'],
                        "requires_upgrade": True,
                        "limit": access_check.get('limit'),
                        "current": access_check.get('current')
                    }, 
                    status=status.HTTP_403_FORBIDDEN
                )

            image_file = request.FILES.get("image")
            if not image_file:
                return Response(
                    {"detail": "No image uploaded."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Processing image for user {request.user.id}: {image_file.name}, size: {image_file.size} bytes")

            # Process image for OpenAI API BEFORE saving to database
            try:
                processed_image_data = validate_and_process_image(image_file)
            except ValueError as e:
                return Response(
                    {"detail": str(e)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Call OpenAI with processed image data
            result = call_openai_vision_return_json(processed_image_data)
            
            if "error" in result:
                return Response(
                    {"detail": result["error"]}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Save to StockImage linked to user AFTER successful OpenAI call
            try:
                from .models import StockImage
                stock_image = StockImage.objects.create(
                    user=request.user,
                    image=image_file
                )
                logger.info(f"Saved StockImage with ID: {stock_image.id}")
                result["stock_image_id"] = stock_image.id
                
                # Add usage info to response
                result["usage_info"] = {
                    "current_usage": access_check.get('current', 0) + 1,
                    "monthly_limit": access_check.get('limit'),
                    "remaining": access_check.get('limit') - (access_check.get('current', 0) + 1) if access_check.get('limit') else None
                }
                
            except Exception as e:
                logger.warning(f"Failed to save StockImage: {e}")
            
            logger.info(f"Returning {len(result.get('items', []))} recognized items")
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in AIRecognizeAPIView: {e}")
            return Response(
                {"detail": "An error occurred while processing the image."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AICommitAPIView(APIView):
    """
    POST JSON: {"items":[{name,quantity,category,price,cost},...]}
    Upserts Products for the authenticated user:
      - matches by name and user (case-insensitive), creates if not found
      - quantity += provided quantity
      - sets price/cost if provided
      - sets category (get_or_create by name) if provided
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        try:
            # Debug: Check if user is properly authenticated
            if not request.user or not request.user.is_authenticated:
                logger.error("User not authenticated in AICommitAPIView")
                return Response(
                    {"detail": "Authentication required."}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            logger.info(f"Processing items for authenticated user: {request.user.id} ({request.user.username})")
            
            # Get user's profile for logging
            try:
                user_profile = request.user.profile
                logger.info(f"User has profile: {user_profile.id}")
            except Exception as e:
                logger.warning(f"User {request.user.id} has no profile: {e}")
            
            # Validate request data structure
            if not isinstance(request.data, dict) or 'items' not in request.data:
                return Response(
                    {"detail": "Request must contain 'items' array."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            items_data = request.data['items']
            if not isinstance(items_data, list):
                return Response(
                    {"detail": "'items' must be an array."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(items_data) == 0:
                return Response(
                    {"detail": "No items provided to save."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            created_count = 0
            updated_count = 0
            saved_items = []
            errors = []

            logger.info(f"Processing {len(items_data)} items for user {request.user.id}")

            # Process items in a transaction
            with transaction.atomic():
                for idx, item in enumerate(items_data):
                    try:
                        # Validate and extract item data
                        name = str(item.get("name", "")).strip()
                        if not name:
                            errors.append(f"Item {idx + 1}: Name is required")
                            continue

                        # Validate quantity
                        try:
                            qty = int(item.get("quantity", 1))
                            qty = max(qty, 0)  # Allow 0 for out-of-stock items
                        except (ValueError, TypeError):
                            qty = 1

                        # Extract optional fields
                        category_name = str(item.get("category", "")).strip()
                        
                        price = None
                        if "price" in item and item["price"] is not None:
                            try:
                                price = Decimal(str(item["price"]))
                                if price < 0:
                                    price = Decimal("0")
                            except (InvalidOperation, ValueError):
                                errors.append(f"Item {idx + 1}: Invalid price value")
                                continue

                        cost = None
                        if "cost" in item and item["cost"] is not None:
                            try:
                                cost = Decimal(str(item["cost"]))
                                if cost < 0:
                                    cost = Decimal("0")
                            except (InvalidOperation, ValueError):
                                errors.append(f"Item {idx + 1}: Invalid cost value")
                                continue

                        # Get user's profile
                        user_profile = None
                        try:
                            from .models import Profile  # Import your Profile model
                            user_profile = request.user.profile  # Assuming one-to-one relationship
                            logger.info(f"Found profile for user {request.user.id}: {user_profile.id}")
                        except Exception as e:
                            logger.warning(f"Could not get profile for user {request.user.id}: {e}")
                            # You might want to create a profile here if it doesn't exist
                            # user_profile = Profile.objects.create(user=request.user)

                        # Handle category (per user/profile)
                        category_obj = None
                        if category_name:
                            from .models import Category  # Import your Category model
                            category_obj, _ = Category.objects.get_or_create(
                                name__iexact=category_name,
                                user=request.user,  # Assuming categories are per user
                                defaults={"name": category_name, "user": request.user}
                            )

                        # Generate unique item code
                        def generate_item_code(user_id, name):
                            """Generate a unique item code based on user and product name"""
                            import uuid
                            import hashlib
                            
                            # Create a short hash from user_id and product name
                            hash_input = f"{user_id}_{name.lower()}"
                            hash_obj = hashlib.md5(hash_input.encode())
                            short_hash = hash_obj.hexdigest()[:8].upper()
                            
                            # Format: USER{user_id}_{short_hash}
                            return f"USER{user_id}_{short_hash}"

                        item_code = generate_item_code(request.user.id, name)
                        
                        # Get or create product for this user and profile
                        from .models import Product  # Import your Product model
                        
                        product, created = Product.objects.get_or_create(
                            name__iexact=name,
                            user=request.user,  # Products are per user
                            profile=user_profile,  # Products are also per profile
                            defaults={
                                "name": name,
                                "user": request.user,  # Explicitly set user
                                "profile": user_profile,  # Explicitly set profile
                                "item_code": item_code,  # Set generated item code
                                "quantity": qty,
                                "original_quantity": qty,
                                "category": category_obj,
                                "price": price if price is not None else Decimal("0"),
                                "cost": cost if cost is not None else Decimal("0"),
                                "status": "OUT" if qty <= 0 else "IN",
                            },
                        )

                        if created:
                            created_count += 1
                            logger.info(f"Created new product for user {request.user.id} (profile: {user_profile.id if user_profile else 'None'}): {name} with item_code: {item_code}")
                        else:
                            # Update existing product
                            updated_fields = []
                            
                            # Ensure user is set (in case of data migration issues)
                            if not product.user:
                                product.user = request.user
                                updated_fields.append("user")
                                logger.info(f"Updated missing user for product: {name}")
                            
                            # Ensure profile is set (in case of data migration issues)
                            if not product.profile and user_profile:
                                product.profile = user_profile
                                updated_fields.append("profile")
                                logger.info(f"Updated missing profile for product: {name}")
                            
                            # Ensure item_code is set (in case of data migration issues)
                            if not product.item_code:
                                product.item_code = item_code
                                updated_fields.append("item_code")
                                logger.info(f"Updated missing item_code for product: {name}")
                            
                            # Update quantity (add to existing)
                            if qty > 0:
                                Product.objects.filter(pk=product.pk).update(
                                    quantity=F("quantity") + qty
                                )
                                updated_fields.append("quantity")
                            
                            # Refresh to get updated quantity
                            product.refresh_from_db()
                            
                            # Update other fields if provided
                            save_needed = False
                            if price is not None and product.price != price:
                                product.price = price
                                updated_fields.append("price")
                                save_needed = True
                                
                            if cost is not None and product.cost != cost:
                                product.cost = cost
                                updated_fields.append("cost")
                                save_needed = True
                                
                            if category_obj and (not product.category or product.category.id != category_obj.id):
                                product.category = category_obj
                                updated_fields.append("category")
                                save_needed = True

                            # Update status based on quantity
                            new_status = "OUT" if product.quantity <= 0 else "IN"
                            if product.status != new_status:
                                product.status = new_status
                                updated_fields.append("status")
                                save_needed = True

                            if save_needed:
                                product.save()
                                
                            updated_count += 1
                            logger.info(f"Updated product for user {request.user.id}: {name}, fields: {updated_fields}")

                        # Add to saved items list
                        saved_items.append({
                            "id": product.id,
                            "name": product.name,
                            "item_code": product.item_code,
                            "quantity": product.quantity,
                            "original_quantity": product.quantity,
                            "price": str(product.price),
                            "cost": str(product.cost),
                            "category": product.category.name if product.category else "",
                            "status": product.status,
                            "user_id": product.user.id if product.user else None,
                            "profile_id": product.profile.id if product.profile else None,
                        })

                    except Exception as e:
                        logger.error(f"Error processing item {idx + 1} ({item}) for user {request.user.id}: {e}")
                        errors.append(f"Item {idx + 1}: {str(e)}")
                        continue

            response_data = {
                "created": created_count,
                "updated": updated_count,
                "items": saved_items,
            }
            
            if errors:
                response_data["errors"] = errors
                logger.warning(f"Completed with errors for user {request.user.id}: {errors}")

            logger.info(f"Successfully saved items for user {request.user.id}: created={created_count}, updated={updated_count}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in AICommitAPIView for user {request.user.id}: {e}")
            return Response(
                {"detail": "An error occurred while saving items."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


# AI Feature Views

@csrf_exempt
@require_POST
def ai_chat_endpoint(request):
    """Simple AI chat endpoint"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Get business data
        business_data = get_business_data(request.user)
        
        # Generate AI response
        ai_response = generate_ai_response(user_message, business_data)
        
        return JsonResponse({
            'success': True,
            'response': ai_response
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    except Exception as e:
        logger.error(f"AI Chat Error: {str(e)}")
        return JsonResponse({
            'error': 'Something went wrong. Please try again.'
        }, status=500)


def get_business_data(user):
    """Get essential business metrics - simple and focused"""
    
    products = Product.objects.filter(user=user)
    today = timezone.now()
    
    # Time periods
    month_ago = today - timedelta(days=30)
    week_ago = today - timedelta(days=7)
    year_ago = today - timedelta(days=365)
    
    # Basic counts
    total_products = products.count()
    in_stock = products.filter(status='IN', quantity__gt=0)
    out_of_stock = products.filter(status='OUT')
    
    # Stock alerts
    low_stock = in_stock.filter(quantity__lte=5)
    critical_stock = in_stock.filter(quantity__lte=2)
    
    # Financial calculations
    def get_value(product):
        try:
            return float(product.price) * product.quantity
        except:
            return 0
    
    def get_cost(product):
        try:
            return float(product.cost) * product.quantity
        except:
            return 0
    
    def safe_price(product):
        try:
            return float(product.price)
        except:
            return 0
    
    def safe_cost(product):
        try:
            return float(product.cost)
        except:
            return 0
    
    # Current inventory
    inventory_value = sum(get_value(p) for p in in_stock)
    inventory_cost = sum(get_cost(p) for p in in_stock)
    potential_profit = inventory_value - inventory_cost
    
    # CALCULATE SALES - THREE METHODS TO CATCH ALL SCENARIOS
    all_products = products
    
    total_sold = 0
    sales_revenue = 0
    sales_cost = 0
    
    # Method 1: Products with original_quantity set (products that had stock reduced)
    for product in all_products:
        # Check if original_quantity exists and is greater than current quantity
        if hasattr(product, 'original_quantity') and product.original_quantity:
            if product.original_quantity > 0 and product.quantity < product.original_quantity:
                sold_qty = product.original_quantity - product.quantity
                total_sold += sold_qty
                sales_revenue += safe_price(product) * sold_qty
                sales_cost += safe_cost(product) * sold_qty
    
    # Method 2: OUT OF STOCK products (assuming they were all sold)
    for product in out_of_stock:
        # If no original_quantity, assume current quantity is what was sold
        if not hasattr(product, 'original_quantity') or not product.original_quantity or product.original_quantity == 0:
            # This product is out of stock, so whatever quantity it shows is likely what was there
            if product.quantity > 0:
                total_sold += product.quantity
                sales_revenue += safe_price(product) * product.quantity
                sales_cost += safe_cost(product) * product.quantity
    
    profit_made = sales_revenue - sales_cost
    
    # Monthly breakdown - Calculate sales per month from ALL historical data
    monthly_data = {}
    for product in all_products:
        if product.original_quantity and product.original_quantity > 0:
            sold_qty = max(0, product.original_quantity - product.quantity)
            if sold_qty > 0:
                # Get month key (e.g., "2024-08", "2024-09")
                month_key = product.date_added.strftime('%Y-%m')
                month_name = product.date_added.strftime('%B %Y')  # e.g., "August 2024"
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'name': month_name,
                        'revenue': 0,
                        'profit': 0,
                        'units_sold': 0
                    }
                
                try:
                    revenue = float(product.price) * sold_qty
                    cost = float(product.cost) * sold_qty
                    monthly_data[month_key]['revenue'] += revenue
                    monthly_data[month_key]['profit'] += revenue - cost
                    monthly_data[month_key]['units_sold'] += sold_qty
                except:
                    pass
    
    # This month's data (current calendar month)
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_products = all_products.filter(date_added__gte=current_month_start)
    month_revenue = 0
    month_profit = 0
    
    for product in month_products:
        if product.original_quantity and product.original_quantity > 0:
            sold_qty = max(0, product.original_quantity - product.quantity)
            if sold_qty > 0:
                try:
                    month_revenue += float(product.price) * sold_qty
                    month_profit += (float(product.price) - float(product.cost)) * sold_qty
                except:
                    pass
    
    # This week's data
    week_products = all_products.filter(date_added__gte=week_ago)
    week_added = week_products.count()
    
    # Top sellers from ALL history
    top_sellers = []
    for product in all_products:
        if product.original_quantity and product.original_quantity > 0:
            sold_qty = max(0, product.original_quantity - product.quantity)
            if sold_qty > 0:
                try:
                    revenue = float(product.price) * sold_qty
                    top_sellers.append({
                        'name': product.name,
                        'sold': sold_qty,
                        'revenue': revenue
                    })
                except:
                    pass
    
    top_sellers.sort(key=lambda x: x['revenue'], reverse=True)
    
    # Get business name
    business_name = 'Your Business'
    try:
        if hasattr(user, 'profile') and user.profile:
            business_name = user.profile.business_name or business_name
    except:
        pass
    
    return {
        'business_name': business_name,
        
        # Inventory
        'total_products': total_products,
        'in_stock_count': in_stock.count(),
        'out_of_stock_count': out_of_stock.count(),
        'low_stock_count': low_stock.count(),
        'critical_stock_count': critical_stock.count(),
        
        # Low stock items for display
        'low_stock_items': [
            f"{p.name} ({p.quantity} left)"
            for p in low_stock[:5]
        ],
        'low_stock_items_display': [
            {'name': p.name, 'current_quantity': p.quantity, 'original_quantity': p.original_quantity}
            for p in low_stock[:3]
        ],
        'critical_stock_items': [
            {'name': p.name, 'current_quantity': p.quantity}
            for p in critical_stock[:3]
        ],
        
        # Financial - Current
        'inventory_value': inventory_value,
        'potential_profit': potential_profit,
        
        # Financial - ALL TIME Sales
        'total_sold': total_sold,
        'total_revenue': sales_revenue,
        'profit_made': profit_made,
        
        # Time-based - Current month
        'month_revenue': month_revenue,
        'month_profit': month_profit,
        'week_products_added': week_added,
        
        # Monthly breakdown (all months)
        'monthly_breakdown': monthly_data,
        
        # Top performers
        'top_sellers': top_sellers[:5],
        
        # Categories
        'categories': list(
            products.values('category__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
    }


def generate_ai_response(user_message, data):
    """Generate AI response using OpenAI"""
    
    # Build monthly breakdown text
    monthly_text = ""
    if data.get('monthly_breakdown'):
        monthly_text = "\n\nMONTHLY BREAKDOWN:\n"
        for month_key in sorted(data['monthly_breakdown'].keys(), reverse=True):
            month_info = data['monthly_breakdown'][month_key]
            monthly_text += f"- {month_info['name']}: R{month_info['revenue']:,.2f} revenue, R{month_info['profit']:,.2f} profit, {month_info['units_sold']} units sold\n"
    
    # Build a simple context
    context = f"""Business: {data['business_name']}

INVENTORY:
- Total Products: {data['total_products']}
- In Stock: {data['in_stock_count']}
- Out of Stock: {data['out_of_stock_count']}
- Low Stock: {data['low_stock_count']} items
- Critical Stock: {data['critical_stock_count']} items

FINANCIAL - ALL TIME:
- Total Revenue Made: R{data['total_revenue']:,.2f}
- Total Profit Made: R{data['profit_made']:,.2f}
- Total Units Sold: {data['total_sold']}
- Current Inventory Value: R{data['inventory_value']:,.2f}
- Potential Profit in Stock: R{data['potential_profit']:,.2f}

THIS MONTH (Current):
- Revenue: R{data['month_revenue']:,.2f}
- Profit: R{data['month_profit']:,.2f}

THIS WEEK:
- Products Added: {data['week_products_added']}
{monthly_text}
LOW STOCK ITEMS:
{chr(10).join(data['low_stock_items']) if data['low_stock_items'] else 'None'}

TOP SELLERS (All Time):
{chr(10).join([f"- {s['name']}: {s['sold']} sold (R{s['revenue']:,.0f})" for s in data['top_sellers']]) if data['top_sellers'] else 'No sales yet'}

User Question: {user_message}"""

    system_prompt = """You are a helpful business assistant. Answer questions about the business using the data provided.

Rules:
1. Keep answers SHORT and SIMPLE (2-4 sentences max)
2. Use actual numbers from the data
3. Be conversational and friendly
4. When asked about specific months (like "August", "last month", etc.), check the MONTHLY BREAKDOWN section
5. For "this month", use the THIS MONTH section
6. For overall/total performance, use the ALL TIME financial data
7. Mention urgent issues (low stock) when relevant
8. Give practical advice when asked
9. Use Rands (R) for currency

Examples:
- "How much did we make?" → "You've made R15,000 in total profit from 150 units sold across all time."
- "How much did we make in August?" → "In August 2024, you made R5,000 in profit from R8,000 in sales."
- "This month?" → "This month you've made R3,000 in profit from R5,000 in sales."
- "Stock levels?" → "You have 45 products in stock. 3 items are running low and need restocking soon."
"""

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Faster and cheaper for simple queries
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=250,  # Slightly increased for month-specific responses
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"OpenAI Error: {str(e)}")
        # Simple fallback
        return get_simple_fallback(user_message, data)


def get_simple_fallback(message, data):
    """Simple fallback responses when AI is unavailable"""
    msg = message.lower()
    
    # Check for specific month queries
    months = ['january', 'february', 'march', 'april', 'may', 'june', 
              'july', 'august', 'september', 'october', 'november', 'december']
    
    found_month = None
    for month in months:
        if month in msg:
            found_month = month.capitalize()
            break
    
    # If asking about a specific month
    if found_month and data.get('monthly_breakdown'):
        # Find matching month in data
        for month_key, month_info in data['monthly_breakdown'].items():
            if found_month in month_info['name']:
                return f"📊 **{month_info['name']}**: You made **R{month_info['profit']:,.2f}** in profit from **R{month_info['revenue']:,.2f}** in sales. You sold **{month_info['units_sold']} units**."
        
        # Month not found in data
        return f"I don't have any sales data recorded for {found_month}. Sales are tracked from when products are added to your inventory."
    
    # Profit/Revenue questions
    if any(word in msg for word in ['profit', 'make', 'made', 'earn', 'revenue', 'sales']):
        if 'month' in msg and 'this' in msg:
            return f"📊 This month you made **R{data['month_profit']:,.2f}** in profit from **R{data['month_revenue']:,.2f}** in sales."
        else:
            return f"💰 You've made **R{data['profit_made']:,.2f}** in total profit. Your total revenue is **R{data['total_revenue']:,.2f}** from {data['total_sold']} units sold."
    
    # Stock questions
    elif any(word in msg for word in ['stock', 'inventory', 'left', 'low']):
        alert = ""
        if data['critical_stock_count'] > 0:
            alert = f"\n\n⚠️ **{data['critical_stock_count']} items critically low!**"
        elif data['low_stock_count'] > 0:
            alert = f"\n\n⚠️ **{data['low_stock_count']} items running low.**"
        
        return f"📦 You have **{data['in_stock_count']} products** in stock. **{data['out_of_stock_count']} are out of stock**.{alert}"
    
    # Top sellers
    elif any(word in msg for word in ['top', 'best', 'popular', 'selling']):
        if data['top_sellers']:
            top = data['top_sellers'][0]
            return f"🏆 Your top seller is **{top['name']}** with {top['sold']} units sold (R{top['revenue']:,.0f} revenue)."
        else:
            return "You don't have any sales recorded yet."
    
    # Advice
    elif any(word in msg for word in ['advice', 'suggest', 'recommend', 'should', 'help']):
        advice = []
        if data['critical_stock_count'] > 0:
            advice.append(f"🔴 Restock {data['critical_stock_count']} critically low items immediately")
        if data['low_stock_count'] > 0:
            advice.append(f"🟡 Monitor {data['low_stock_count']} items with low stock")
        if data['profit_made'] > 0:
            margin = (data['profit_made'] / data['total_revenue'] * 100) if data['total_revenue'] > 0 else 0
            advice.append(f"💡 Your profit margin is {margin:.1f}% - aim for 30%+")
        
        return "\n".join(advice) if advice else "Keep tracking your inventory and sales regularly!"
    
    # General overview
    else:
        return f"""📊 **Quick Summary:**
• {data['in_stock_count']} products in stock
• R{data['profit_made']:,.2f} profit made (all time)
• {data['total_sold']} units sold
• {data['low_stock_count']} items need attention

Ask me: "How much did we make?", "How much in August?", "Stock levels?", "Top sellers?", "Give me advice" """