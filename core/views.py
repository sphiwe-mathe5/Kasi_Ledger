from collections import defaultdict
import decimal
from django.utils import timezone
import json
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
from django.contrib import messages
from django.db.models.functions import TruncMonth, TruncDate
from core.forms import CategoryForm
from .models import Product, Category, Transaction
from submit.models import Service, Profile
#import cv2
from .models import IncomeStatement
from .forms import IncomeStatementForm
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt
from .models import Product
from decimal import Decimal, InvalidOperation
#from pyzbar.pyzbar import decode
import winsound
from django.urls import reverse, reverse_lazy
import random
from submit.forms import ServiceForm
#from .forms import ProductForm
from django.db.models import Q

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
                #original_quantity=quantity,
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
            #'original_quantity': product.original_quantity,
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
    return render(request, 'core/subscribed.html')


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

@csrf_exempt
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

#.order_by('-date_added')




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

    return render(request, 'core/contact.html', context)



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
