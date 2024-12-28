from collections import defaultdict
import decimal
from django.utils import timezone
import json
import random
from django.template.loader import render_to_string
import logging
from django.db import transaction
from datetime import datetime
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
from django.contrib.auth.hashers import check_password 
from django.contrib import messages
from django.db.models.functions import TruncMonth, TruncDate
from core.forms import CategoryForm
from .models import Product, Category, Transaction, EmailTemplate, SentEmail
from submit.models import Profile, Subscription, SubscriptionPlan, ProductPeriod
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import io
import barcode  
from django.views.decorators.http import require_GET
from barcode.writer import ImageWriter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO
from django.db.models import Q
from .models import IncomeStatement
from .forms import IncomeStatementForm
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
from .models import Product, Sale, SaleItem, Barcode
from decimal import Decimal, InvalidOperation

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

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib import messages
from .forms import EmailForm
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)


def index(request):
    return render(request, 'core/index.html')

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

        if action == 'in':

            subscription = Subscription.objects.filter(
                user=user, 
                status__in=['active', 'cancelled']  
            ).first()
            
            if not subscription:
                return JsonResponse({
                    'success': False,
                    'message': 'Subscription required',
                    'details': {
                        'type': 'no_subscription',
                        'title': 'Subscription Required',
                        'description': 'You need to subscribe to a plan to use this feature. Choose between our Free or Pro plans.',
                        'action_url': reverse('subscription_plans'),  
                        'action_text': 'View Plans'
                    }
                })
            
            
            active_subscription = Subscription.objects.filter(
                user=user, 
                status='active'
            ).first()
            
            if not active_subscription:
                return JsonResponse({
                    'success': False,
                    'message': 'Inactive subscription',
                    'details': {
                        'type': 'inactive_subscription',
                        'title': 'Inactive Subscription',
                        'description': 'Your subscription is currently inactive. Please reactivate your subscription to continue.',
                        'action_url': reverse('subscription_settings'),  
                        'action_text': 'Manage Subscription'
                    }
                })

            
            current_period = ProductPeriod.get_or_create_current_period(profile)
            
            if current_period.product_count >= active_subscription.plan.product_limit:
                days_until_reset = (current_period.end_date - timezone.now()).days
                return JsonResponse({
                    'success': False,
                    'message': 'Product limit reached',
                    'details': {
                        'type': 'limit_reached',
                        'limit': active_subscription.plan.product_limit,
                        'days_until_reset': days_until_reset,
                        'reset_date': current_period.end_date.strftime('%B %d, %Y')
                    }
                })

            
            current_period.product_count += 1
            current_period.save()
            
            existing_product = Product.objects.filter(barcode=barcode).first()
            if existing_product:
                return JsonResponse({
                    'success':
                    False,
                    'message':
                    'Product with this barcode already exists. Use "Scan Out" to reduce quantity.'
                })

            name = request.POST.get('name')
            price = request.POST.get('price')
            cost = request.POST.get('cost')
            quantity = request.POST.get('quantity')
            category_id = request.POST.get('category')

            if not all([name, price, cost, quantity, category_id]):
                return JsonResponse({
                    'success':
                    False,
                    'message':
                    'All product details including category and quantity are required for scan in.'
                })

            try:
                price = Decimal(price)
                cost = Decimal(cost)
                quantity = int(quantity)
                category = Category.objects.get(id=category_id)
            except InvalidOperation:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid price or cost value.'
                })
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid quantity value.'
                })
            except Category.DoesNotExist:
                return JsonResponse({
                    'success':
                    False,
                    'message':
                    'Selected category does not exist.'
                })

            
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
        else:  
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
                        'success':
                        False,
                        'message':
                        'Product is already out of stock'
                    })
            except Product.DoesNotExist:
                return JsonResponse({
                    'success':
                    False,
                    'message':
                    'Product not found. Please scan in the product first.'
                })

        return JsonResponse({
            'success':True,
            'message':message,
            'status':product.status,
            'name':product.name,
            'price':str(product.total_price),  
            'cost':str(product.total_cost),
            'quantity':product.quantity,
            'original_quantity': product.original_quantity,
            'category':product.category.name if product.category else ''
        })

    return JsonResponse({'success': False, 'message': 'Invalid request'})



def subscribed(request):
    products = Product.objects.filter(profile=request.user.profile)

    context = {
        'products': products,
        
    }
    return render(request, 'core/subscribed.html', context)



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



logger = logging.getLogger(__name__)
def send_receipt_email(email, receipt_data, request):
    user = request.user
    try:
        profile = user.profile  
        company_name = profile.company_name if profile.company_name else ''
    except Profile.DoesNotExist:
        company_name = ''
        return False

    html_content = render_to_string('core/receipt_template.html', {
        'items': receipt_data['items'],
        'total': receipt_data['total'],
        'date': receipt_data['date'],
        'money_rendered': receipt_data['money_rendered'],
        'change': receipt_data['change'],
        'user': {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'company_name': user.company_name
        }
    })
    
    try:
        send_mail(
            subject='Your Purchase Receipt',
            message='Please see the attached receipt for your recent purchase.',
            from_email=user.email,
            recipient_list=[email],
            html_message=html_content,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
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
                try:
                    product = Product.objects.select_for_update().get(
                        barcode=item['barcode'],
                        status='IN',
                        profile=request.profile
                    )
                except Product.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': f'Product with barcode {item["barcode"]} not found or does not belong to you'
                    })

                quantity = Decimal(str(item['quantity']))
                
                if product.quantity < quantity:
                    raise ValueError(f"Insufficient stock for product: {product.name}")
                
                item_total = product.unit_price * quantity
                total += item_total
                
                product.quantity -= quantity
                product.status = 'OUT' if product.quantity == 0 else 'IN'
                product.save()
                
                product_details.append({
                    'name': product.name,
                    'price': float(product.unit_price),
                    'quantity': float(quantity),
                    'total': float(item_total)
                })

            
            if money_rendered < total:
                raise ValueError("Insufficient money rendered")
                
            change = money_rendered - total

            receipt_data = {
                'items': product_details,
                'total': float(total),
                'money_rendered': float(money_rendered),
                'change': float(change),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'seller': request.user.username
            }
            
            email_sent = False
            if customer_email:
                email_sent = send_receipt_email(
                    email=customer_email,
                    receipt_data=receipt_data,
                    request=request  
                )

            return JsonResponse({
                'success': True,
                'receipt_data': receipt_data,
                'email_sent': email_sent
            })

    except Exception as e:
        print(f"Error processing sale: {str(e)}")  
        return JsonResponse({'success': False, 'message': str(e)})



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
def contact(request):
    show_modal = True  
    
    if request.method == 'POST':
        entered_password = request.POST.get('admin_password')
        user = request.user
        
        
        if check_password(entered_password, user.admin_password):  
            show_modal = False   
        else:
            messages.error(request, "Incorrect password. Please try again.")

    
    show_all = request.GET.get('show_all') == 'true'
    target_date = request.GET.get('date')
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    
    profile = get_object_or_404(Profile, user=request.user)
    categories = Category.objects.filter(profile=profile)
    
    out_of_stock_count = Product.objects.filter(status='OUT', profile=profile).count()

    
    products = Product.objects.filter(profile=profile)

    
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

    return render(request, 'core/contact.html', {
        'show_modal': show_modal,
        'categories': categories,
        'grouped_products': grouped_products_dict,
        'out_of_stock_count': out_of_stock_count,
        'out_of_stock_per_month': out_of_stock_per_month,
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
    })



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


def list_income_statements(request):
    statements = IncomeStatement.objects.filter(profile__user=request.user)


    context = {
        'statements': statements,
    }
    return render(request, 'core/list_income_statements.html', context)


def guide(request):

    return render(request, 'core/guide.html')

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

        
        enterprise_plan = SubscriptionPlan.objects.get(price=199.99)
        if subscription.plan != enterprise_plan:
            messages.error(request, "You must upgrade to the Enterprise Plan to download barcodes.")
            return render(request, 'core/generate_barcodes.html')

        quantity = int(request.POST.get('quantity', 1))
        format_type = request.POST.get('format', 'pdf')

        generated_codes = []
        for _ in range(quantity):
            code = Barcode.generate_unique_code()
            Barcode.objects.create(code=code)
            generated_codes.append(code)

        if format_type == 'pdf':
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="barcodes.pdf"'
            
            c = canvas.Canvas(response, pagesize=A4)
            width, height = A4
            
            x_start = 20 * mm
            y_start = height - 30 * mm
            barcode_height = 25 * mm
            spacing = 35 * mm
            codes_per_page = 20
            
            with tempfile.TemporaryDirectory() as temp_dir:
                for idx, code in enumerate(generated_codes):
                    if idx > 0 and idx % codes_per_page == 0:
                        c.showPage()
                        y_start = height - 30 * mm
                    
                    ean = barcode.get('ean13', code, writer=ImageWriter())
                    temp_path = os.path.join(temp_dir, f'barcode_{code}.png')
                    
                    img_buffer = BytesIO()
                    ean.write(img_buffer)
                    
                    img_buffer.seek(0)
                    img = Image.open(img_buffer)
                    img.save(temp_path, 'PNG')
                    img_buffer.close()
                    
                    if os.path.exists(temp_path):
                        y_pos = y_start - ((idx % codes_per_page) * spacing)
                        try:
                            c.drawImage(temp_path, x_start, y_pos, width=60*mm, height=barcode_height)
                            c.drawString(x_start, y_pos - 5*mm, code)
                        except Exception as e:
                            print(f"Error drawing image: {e}")
                    else:
                        print(f"File not found: {temp_path}")
                
                c.save()
            
            return response
            
        else:  
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for code in generated_codes:
                    ean = barcode.get('ean13', code, writer=ImageWriter())
                    img_buffer = BytesIO()
                    ean.write(img_buffer)
                    
                    zip_file.writestr(f'barcode_{code}.png', img_buffer.getvalue())
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
        email = request.POST.get('email')

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

        messages.success(request, 'Thank you for Subscribing, a confirmation email has been sent!')
        return redirect('index')

    return redirect('index')