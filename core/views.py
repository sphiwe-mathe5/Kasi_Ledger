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
from django.contrib.auth.hashers import check_password 
from django.contrib import messages
from django.db.models.functions import TruncMonth, TruncDate
from core.forms import CategoryForm
from .models import Product, Category, Transaction
from submit.models import Service, Profile
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import io
import barcode  
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
import winsound
from django.urls import reverse, reverse_lazy
import random
from submit.forms import ServiceForm
from django.db.models import Q
from barcode.writer import ImageWriter
from io import BytesIO
import zipfile
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import tempfile
import os


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

        # Get the currently logged-in user and their profile
        user = request.user
        try:
            profile = user.profile  # Get the user's profile
        except Profile.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User profile not found.'
            })

        if action == 'in':
            # Check if the product already exists for this user's profile
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

            # Create a new product associated with the user's profile
            product = Product.objects.create(
                barcode=barcode,
                name=name,
                price=price,
                cost=cost,
                quantity=quantity,
                original_quantity=quantity,
                status='IN',
                category=category,
                profile=profile  # Use the profile instance directly
            )

            message = f'Product scanned in successfully. Quantity: {quantity}'
        else:  # 'out'
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
            'price':str(product.total_price),  # Using total_price property
            'cost':str(product.total_cost),
            'quantity':product.quantity,
            'original_quantity': product.original_quantity,
            'category':product.category.name if product.category else ''
        })

    return JsonResponse({'success': False, 'message': 'Invalid request'})


@csrf_exempt
def bulk_subscribe(request):
    if request.method == 'POST':
        barcode = request.POST.get('barcode')
        name = request.POST.get('name')
        quantity = request.POST.get('quantity')
        price = request.POST.get('price')
        cost = request.POST.get('cost')
        category_id = request.POST.get('category')

        if not all([barcode, name, quantity, price, cost, category_id]):
            return JsonResponse({'success': False, 'message': 'All fields are required for bulk scan.'})

        try:
            quantity = int(quantity)
            price = Decimal(price)
            cost = Decimal(cost)
            category = Category.objects.get(id=category_id)
        except (ValueError, InvalidOperation):
            return JsonResponse({'success': False, 'message': 'Invalid quantity, price, or cost value.'})
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Selected category does not exist.'})

        if quantity <= 0:
            return JsonResponse({'success': False, 'message': 'Quantity must be a positive integer.'})

        product, created = Product.objects.update_or_create(
            barcode=barcode,
            defaults={
                'name': name,
                'price': price,
                'cost': cost,
                'status': 'IN',
                'category': category,
                'quantity': quantity  # Add this field to your Product model
            }
        )

        message = f'{"Added" if created else "Updated"} {quantity} units of product'

        return JsonResponse({
            'success': True,
            'message': message,
            'status': product.status,
            'name': product.name,
            'price': str(product.price),
            'cost': str(product.cost),
            'category': product.category.name,
            'quantity': product.quantity
        })

    return JsonResponse({'success': False, 'message': 'Invalid request'})

def subscribed(request):
    products = Product.objects.filter(profile=request.user.profile)

    context = {
        'products': products,
        # Add other context data as needed
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

'''@csrf_exempt
def process_sale(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})

    try:
        data = json.loads(request.body)
        items = data.get('items', [])

        with transaction.atomic():
            total = Decimal('0')
            for item in items:
                product = Product.objects.select_for_update().get(
                    barcode=item['barcode'], status='IN')

                if product.quantity < item['quantity']:
                    return JsonResponse({
                        'success':
                        False,
                        'message':
                        f'Insufficient stock for {product.name}'
                    })

                total += product.unit_price * Decimal(str(item['quantity']))
                product.quantity -= item['quantity']
                product.status = 'OUT' if product.quantity == 0 else 'IN'
                product.save()

            return JsonResponse({
                'success':
                True,
                'message':
                f'Sale completed. Total: R{total:.2f}'
            })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

#.order_by('-date_added')'''


logger = logging.getLogger(__name__)
def send_receipt_email(email, receipt_data, request):
    """Send receipt to customer's email using sender's profile email."""
    # Get user and profile
    user = request.user
    try:
        profile = user.profile  # Get the user's profile
        company_name = profile.company_name if profile.company_name else ''
    except Profile.DoesNotExist:
        company_name = ''
        return False

    html_content = render_to_string('core/receipt_template.html', {
        'items': receipt_data['items'],
        'total': receipt_data['total'],
        'date': receipt_data['date'],
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
from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

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

# Modified process_sale view with authorization
@csrf_exempt
@require_profile
def process_sale(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})

    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        customer_email = data.get('email')
        
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
                
                # Update product stock
                product.quantity -= quantity
                product.status = 'OUT' if product.quantity == 0 else 'IN'
                product.save()
                
                product_details.append({
                    'name': product.name,
                    'price': float(product.unit_price),
                    'quantity': float(quantity),
                    'total': float(item_total)
                })

            receipt_data = {
                'items': product_details,
                'total': float(total),
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'seller': request.user.username
            }

            # Send email if customer email is provided
            email_sent = False
            if customer_email:
                email_sent = send_receipt_email(
                    email=customer_email,
                    receipt_data=receipt_data,
                    request=request  # Changed from profile=profile to request=request
                )

            return JsonResponse({
                'success': True,
                'receipt_data': receipt_data,
                'email_sent': email_sent
            })

    except Exception as e:
        print(f"Error processing sale: {str(e)}")  # For debugging
        return JsonResponse({'success': False, 'message': str(e)})
def download_receipt(request):
    # Implement session-based or temporary storage for the PDF
    # Return the PDF file
    try:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="receipt.pdf"'
        # Get the PDF content from your storage mechanism
        # Write it to the response
        return response
    except Exception as e:
        logger.error("Error downloading receipt: %s", str(e))
        return JsonResponse({
            'success': False,
            'message': 'Failed to download receipt'
        })

logger = logging.getLogger(__name__)

def generate_receipt_pdf(product_details, total):
    """
    Generate a PDF receipt with proper error handling and validation.
    """
    try:
        # Create a new buffer
        buffer = io.BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
            title="Sales Receipt"  # Add PDF metadata
        )
        
        # Initialize story and styles
        story = []
        styles = getSampleStyleSheet()
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1
        )
        
        # Add title
        title = Paragraph("Sales Receipt", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Prepare table data with validation
        table_data = [['Product', 'Price (R)', 'Quantity', 'Total (R)']]
        
        # Add product rows with data validation
        for item in product_details:
            # Validate and format each field
            name = str(item.get('name', ''))[:40]  # Limit name length
            price = f"{float(item.get('price', 0)):.2f}"
            quantity = f"{int(float(item.get('quantity', 0)))}"
            total_price = f"{float(item.get('total_price', 0)):.2f}"
            
            table_data.append([name, price, quantity, total_price])
        
        # Add total row
        table_data.append(['', '', 'Total:', f"{float(total):.2f}"])
        
        # Create and style the table
        table = Table(
            table_data,
            colWidths=[4*inch, 1.2*inch, 1*inch, 1.2*inch],
            repeatRows=1  # Repeat header row on new pages
        )
        
        # Define table styles
        table_style = TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -2), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
            
            # Total row
            ('BACKGROUND', (0, -1), (-1, -1), colors.grey),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
        ])
        
        table.setStyle(table_style)
        story.append(table)
        
        # Add footer
        story.append(Spacer(1, 30))
        footer_text = "Thank you for your purchase!"
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=12,
            alignment=1
        )
        footer = Paragraph(footer_text, footer_style)
        story.append(footer)
        
        # Build the PDF
        doc.build(story)
        
        # Get PDF value and create response
        pdf_value = buffer.getvalue()
        buffer.close()
        
        # Create and return response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="receipt.pdf"'
        response.write(pdf_value)
        
        return response
        
    except Exception as e:
        logger.error("PDF generation error: %s", str(e), exc_info=True)
        raise Exception(f"Failed to generate PDF: {str(e)}")


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



#def subscribed(request):
#    products = Product.objects.filter(status='IN')
#    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#        return HttpResponse(render(request, 'core/subscribed.html',{'products': products}))
#    return render(request, 'core/subscribed.html', {'products': products}




# View to create an Income Statement
@login_required
def create_income_statement(request):
    show_all = request.GET.get('show_all') == 'true'
    target_date = request.GET.get('date')
    out_of_stock_count = Product.objects.filter(status='OUT').count()

    categories = Category.objects.all()

    # Calculate out-of-stock count per month
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

        # Update monthly totals
        monthly_totals[product.month]['price'] += product.price
        monthly_totals[product.month]['cost'] += product.cost
        monthly_totals[product.month]['profit_loss'] += product.profit_loss

    # Create month choices after populating monthly_totals
    month_choices = [(month.strftime('%Y-%m'), month.strftime('%B %Y')) for month in monthly_totals.keys()]
    monthly_totals_json = {month.strftime('%Y-%m'): {
        'price': str(monthly_totals[month]['price']),
        'cost': str(monthly_totals[month]['cost']),
    } for month in monthly_totals.keys()}


    # Convert defaultdict to regular dict for template rendering
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

            # Calculate daily totals
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
            income_statement = form.save(commit=False)  # Don't save yet; we need to associate it with a profile

            # Associate the income statement with the user's profile
            profile = Profile.objects.get(user=request.user)  # Get the user's profile
            income_statement.profile = profile  # Assuming your IncomeStatement model has a ForeignKey to Profile

            income_statement.save()  # Now save the income statement

            # After saving, redirect to view the created income statement
            return redirect('view_income_statement', pk=income_statement.pk)
    else:
        form = IncomeStatementForm()

    # Pass the context to the template
    context = {
        'form': form,
        'month_choices': month_choices,
        'monthly_totals': monthly_totals,
        'monthly_totals_json': json.dumps(monthly_totals_json),
    }

    return render(request, 'core/create_income_statement.html', context)

# View to display the calculated income statement
@login_required  # Ensure this view is protected as well
def view_income_statement(request, pk):
    statements = IncomeStatement.objects.filter(profile__user=request.user)  # Retrieve only statements associated with the logged-in user's profile

    context = {
        'statements': statements,
    }

    return render(request, 'core/list_income_statements.html', context)

@login_required
def terms(request):

    show_all = request.GET.get('show_all') == 'true'
    target_date = request.GET.get('date')
    out_of_stock_count = Product.objects.filter(status='OUT').count()
    # Get the user's profile
    profile = Profile.objects.get(user=request.user)  # Get the logged-in user's profile

    categories = Category.objects.filter(profile=profile)
    # Filter products by the user's profile
    products = Product.objects.filter(profile=profile).annotate(
        month=TruncMonth('date_added'),
        date=TruncDate('date_added')).order_by('-date_added')

    # Calculate out-of-stock count per month for this user's products
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

        # Update monthly totals
        monthly_totals[product.month]['price'] += product.price
        monthly_totals[product.month]['cost'] += product.cost
        monthly_totals[product.month]['profit_loss'] += product.profit_loss

    # Convert defaultdict to regular dict for template rendering
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

            # Calculate daily totals
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

    context = {
        'categories': categories,
        'grouped_products': grouped_products_dict,
        'out_of_stock_count': out_of_stock_count,
        'out_of_stock_per_month': out_of_stock_per_month,
    }


    return render(request, 'core/terms.html',context)



def unsubscribed(request):
    categories = Category.objects.all().order_by('name')
    categories_data = [{'id': category.id, 'name': category.name} for category in categories]
    return JsonResponse({'success': True, 'categories': categories_data})

@login_required
def contact(request):
    show_modal = True  # Default to showing the modal
    
    if request.method == 'POST':
        entered_password = request.POST.get('admin_password')
        user = request.user
        
        # Check if the entered password matches the stored admin_password
        if check_password(entered_password, user.admin_password):  # Use check_password if hashed
            show_modal = False  # Set to False if the password is correct
            messages.success(request, "Password accepted.")  # Optional success message
        else:
            messages.error(request, "Incorrect password. Please try again.")

    # Handle GET parameters for filtering and searching
    show_all = request.GET.get('show_all') == 'true'
    target_date = request.GET.get('date')
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    # Get profile and categories safely
    profile = get_object_or_404(Profile, user=request.user)
    categories = Category.objects.filter(profile=profile)
    
    out_of_stock_count = Product.objects.filter(status='OUT', profile=profile).count()

    # Base queryset for products
    products = Product.objects.filter(profile=profile)

    # Apply filters based on search query and selected filters
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    if category_filter:
        products = products.filter(category__name=category_filter)
        
    if status_filter:
        products = products.filter(status=status_filter)

    # Annotate and order by date added
    products = products.annotate(
        month=TruncMonth('date_added'),
        date=TruncDate('date_added')
    ).order_by('-date_added')

    # Calculate out_of_stock_per_month for reporting
    out_of_stock_per_month = Product.objects.filter(profile=profile, status='OUT').annotate(
        month=TruncMonth('date_added')
    ).values('month').annotate(count=Count('id')).order_by('month')

    grouped_products = defaultdict(lambda: defaultdict(list))
    monthly_totals = defaultdict(lambda: {'price': Decimal('0.00'), 'cost': Decimal('0.00'), 'profit_loss': Decimal('0.00')})

    # Grouping logic for products
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

    # Convert to dict for template rendering
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




from django.views.decorators.http import require_GET

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


def inbox(request):

    return render(request, 'core/inbox.html')


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
        
    # Get unique categories for dropdown
    categories = Product.objects.values_list('category', flat=True).distinct()
    
    # Organize by date (assuming you have this logic)
    month_data = organize_products_by_date(products)  # Your existing organization function
    
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
        quantity = int(request.POST.get('quantity', 1))
        format_type = request.POST.get('format', 'pdf')
        
        # Generate barcodes
        generated_codes = []
        for _ in range(quantity):
            code = Barcode.generate_unique_code()
            Barcode.objects.create(code=code)
            generated_codes.append(code)
        
        if format_type == 'pdf':
            # Generate PDF
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="barcodes.pdf"'
            
            # Create PDF
            c = canvas.Canvas(response, pagesize=A4)
            width, height = A4
            
            # Position variables
            x_start = 20 * mm
            y_start = height - 30 * mm
            barcode_height = 25 * mm
            spacing = 35 * mm
            codes_per_page = 20
            
            # Create a temporary directory to store barcode images
            with tempfile.TemporaryDirectory() as temp_dir:
                for idx, code in enumerate(generated_codes):
                    # Create new page if needed
                    if idx > 0 and idx % codes_per_page == 0:
                        c.showPage()
                        y_start = height - 30 * mm
                    
                    # Generate barcode image
                    ean = barcode.get('ean13', code, writer=ImageWriter())
                    temp_path = os.path.join(temp_dir, f'barcode_{code}.png')
                    
                    # Save barcode to BytesIO first
                    img_buffer = BytesIO()
                    ean.write(img_buffer)
                    
                    # Convert to PIL Image and save as PNG
                    img_buffer.seek(0)
                    img = Image.open(img_buffer)
                    img.save(temp_path, 'PNG')
                    img_buffer.close()
                    
                    # Verify file exists and is readable
                    if os.path.exists(temp_path):
                        # Add to PDF
                        y_pos = y_start - ((idx % codes_per_page) * spacing)
                        try:
                            c.drawImage(temp_path, x_start, y_pos, width=60*mm, height=barcode_height)
                            c.drawString(x_start, y_pos - 5*mm, code)
                        except Exception as e:
                            print(f"Error drawing image: {e}")
                            print(f"File path: {temp_path}")
                            print(f"File exists: {os.path.exists(temp_path)}")
                            print(f"File size: {os.path.getsize(temp_path)}")
                    else:
                        print(f"File not found: {temp_path}")
                
                c.save()
            return response
            
        else:  # ZIP file with individual images
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for code in generated_codes:
                    # Generate barcode image
                    ean = barcode.get('ean13', code, writer=ImageWriter())
                    img_buffer = BytesIO()
                    ean.write(img_buffer)
                    
                    # Add to ZIP
                    zip_file.writestr(f'barcode_{code}.png', img_buffer.getvalue())
                    img_buffer.close()
            
            response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="barcodes.zip"'
            zip_buffer.close()
            return response
    
    return render(request, 'core/generate_barcodes.html')