from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Employee, Service, ServiceTicket
from .forms import EmployeeForm, ServiceForm, ServiceTicketForm, ServiceTicketUpdateForm
from datetime import datetime, timedelta
from django.db.models.functions import TruncMonth
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import openai
import logging
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from saloon.decorators import company_category_required

from django.core.cache import cache

logger = logging.getLogger(__name__)
# Dashboard View
@login_required
@company_category_required('car_wash')
def dashboard(request):
    """Carwash dashboard with AI chatbot"""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    user = request.user
    
    # Check subscription access for tickets and chatbot
    from saloon.subscriptions import check_feature_access
    
    ticket_access = check_feature_access(user, 'appointments')  # Reusing appointments for tickets
    chatbot_access = check_feature_access(user, 'chatbot')
    
    # Get all the same data as the regular dashboard
    total_employees = Employee.objects.filter(is_active=True, created_by=user).count()
    total_services = Service.objects.filter(is_active=True, created_by=user).count()
    total_tickets = ServiceTicket.objects.filter(created_by=user).count()

    today_tickets = ServiceTicket.objects.filter(created_at__date=today, created_by=user)
    today_revenue = today_tickets.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0

    month_tickets = ServiceTicket.objects.filter(created_at__date__gte=start_of_month, created_by=user)
    month_revenue = month_tickets.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0

    recent_tickets = (
        ServiceTicket.objects
        .filter(created_by=user)
        .select_related('service', 'employee')
        .order_by('-created_at')[:10]
    )

    employee_stats = (
        Employee.objects.filter(created_by=user, tickets__created_at__date__gte=start_of_month)
        .annotate(
            cars_washed=Count('tickets'),
            revenue_generated=Sum('tickets__total_amount'),
        )
        .order_by('-cars_washed')[:5]
    )

    # Dynamic section
    search_query = request.GET.get('search', '')
    services = Service.objects.filter(is_active=True, created_by=user)
    if search_query:
        services = services.filter(name__icontains=search_query)

    paginator = Paginator(services, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # FIX: Pass the user to the ServiceTicketForm
    ticket_form = ServiceTicketForm(user=user)

    context = {
        'total_employees': total_employees,
        'total_services': total_services,
        'total_tickets': total_tickets,
        'today_tickets_count': today_tickets.count(),
        'today_revenue': today_revenue,
        'month_tickets_count': month_tickets.count(),
        'month_revenue': month_revenue,
        'recent_tickets': recent_tickets,
        'employee_stats': employee_stats,
        'pending_tickets': ServiceTicket.objects.filter(status='pending', created_by=user).count(),
        'page_obj': page_obj,
        'search_query': search_query,
        'ticket_form': ticket_form,  # Use the form with user passed
        # AI Chatbot context
        'show_ai_chatbot': chatbot_access['allowed'],
        'chatbot_access': chatbot_access,
        'current_time': timezone.now(),
        # Subscription access
        'ticket_access': ticket_access,
        'can_create_ticket': ticket_access['allowed'],
    }

    return render(request, 'carwash/dashboard.html', context)

# Employee Views - Combined Create and List
@login_required
@company_category_required('car_wash')
def employee_list_create(request):
    user = request.user

    # ✅ Handle employee creation
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.created_by = user
            employee.save()
            messages.success(request, f'Employee {employee.full_name} created successfully!')
            return redirect('employee_list_create')
    else:
        form = EmployeeForm()

    # ✅ Handle search and listing — only show this user's employees
    search_query = request.GET.get('search', '')
    employees = Employee.objects.filter(is_active=True, created_by=user)

    if search_query:
        employees = employees.filter(
            Q(name__icontains=search_query)
            | Q(surname__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    # ✅ Add per-employee stats (only their tickets under this user)
    for employee in employees:
        employee.total_cars = employee.tickets.filter(
            status='completed',
            created_by=user  # ensure only tickets from this user’s account
        ).count()

        employee.total_revenue = employee.tickets.filter(
            status='completed',
            created_by=user
        ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Pagination
    paginator = Paginator(employees.order_by('-id'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'form': form,
        'page_obj': page_obj,
        'search_query': search_query,
    }

    return render(request, 'carwash/employee_list_create.html', context)

@login_required
def employee_update_delete(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    
    if request.method == "POST":
        if "delete" in request.POST:
            employee.delete()
            messages.success(request, "Employee deleted successfully!")
        else:
            employee.name = request.POST.get("name")
            employee.surname = request.POST.get("surname")
            employee.phone = request.POST.get("phone")
            employee.email = request.POST.get("email")
            employee.save()
            messages.success(request, "Employee updated successfully!")
        
        return redirect("employee_list_create")

    return render(request, "carwash/employee_form.html", {"employee": employee})


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk, created_by=request.user)

    # Get employee's tickets with pagination
    tickets = employee.tickets.select_related('service').order_by('-created_at')
    paginator = Paginator(tickets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_cars = employee.tickets.filter(status='completed').count()
    total_revenue = employee.tickets.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # This month's stats
    start_of_month = timezone.now().date().replace(day=1)
    month_cars = employee.tickets.filter(
        status='completed',
        created_at__date__gte=start_of_month
    ).count()
    month_revenue = employee.tickets.filter(
        status='completed',
        created_at__date__gte=start_of_month
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'employee': employee,
        'page_obj': page_obj,
        'total_cars': total_cars,
        'total_revenue': total_revenue,
        'month_cars': month_cars,
        'month_revenue': month_revenue,
    }
    
    return render(request, 'carwash/employee_detail.html', context)

# Service Views - Combined Create and List
@login_required
@company_category_required('car_wash')
def service_list_create(request):
    # Handle form submission
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.created_by = request.user
            service.save()
            messages.success(request, f'Service "{service.name}" created successfully!')
            return redirect('dashboard')
    else:
        form = ServiceForm()

    # Handle search and listing
    search_query = request.GET.get('search', '')
    services = Service.objects.filter(is_active=True)
    
    if search_query:
        services = services.filter(name__icontains=search_query)
    
    # Add usage statistics
    for service in services:
        service.usage_count = service.tickets.count()
        service.revenue_generated = service.tickets.filter(
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    paginator = Paginator(services, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'carwash/dashboard.html', context)

@login_required
def service_update_delete(request, pk):
    service = get_object_or_404(Service, pk=pk, created_by=request.user)
    
    # Handle delete request
    if request.method == 'POST' and 'delete' in request.POST:
        service_name = service.name
        service.is_active = False  # Soft delete
        service.save()
        messages.success(request, f'Service "{service_name}" deleted successfully!')
        return redirect('service_list_create')
    
    # Handle update request
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            service = form.save()
            messages.success(request, f'Service "{service.name}" updated successfully!')
            return redirect('service_list_create')
    else:
        form = ServiceForm(instance=service)
    
    context = {
        'form': form,
        'service': service,
        'title': 'Update/Delete Service'
    }
    return render(request, 'carwash/service_update_delete.html', context)

# Service Ticket Views - Combined Create and List
@login_required
@company_category_required('car_wash')
def ticket_list_create(request):
    user = request.user

    if request.method == 'POST':
        form = ServiceTicketForm(request.POST, user=user)  # Pass user to form
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = user
            ticket.save()

            # ✅ Send receipt email (if email exists)
            if ticket.customer_email:
                subject = f"Your Service Ticket #{ticket.ticket_number}"
                from_email = settings.DEFAULT_FROM_EMAIL
                to_email = [ticket.customer_email]

                html_content = render_to_string(
                    "carwash/email_receipt.html",
                    {
                        "ticket": ticket,
                        "company_name": getattr(user, "company_name", "Our"),  # fallback
                    }
                )
                text_content = strip_tags(html_content)

                email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
                email.attach_alternative(html_content, "text/html")
                email.send()

            messages.success(request, f"Service ticket {ticket.ticket_number} created successfully!")
            return redirect("dashboard")
    else:
        form = ServiceTicketForm(user=user)  # Pass user to form

    # ✅ Filters and search (user-specific)
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    # Only tickets belonging to the logged-in user
    tickets = ServiceTicket.objects.select_related('service', 'employee').filter(created_by=user)

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    if search_query:
        tickets = tickets.filter(
            Q(ticket_number__icontains=search_query)
            | Q(car_number_plate__icontains=search_query)
            | Q(customer_email__icontains=search_query)
        )

    paginator = Paginator(tickets.order_by('-created_at'), 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ✅ Monthly summary (only this user's completed tickets)
    monthly_summary = (
        ServiceTicket.objects.filter(status="completed", created_by=user)
        .annotate(month=TruncMonth("completed_at"))
        .values("month")
        .annotate(total_revenue=Sum("total_amount"), count=Count("id"))
        .order_by("-month")
    )

    status_choices = ServiceTicket.STATUS_CHOICES

    context = {
        "form": form,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "search_query": search_query,
        "status_choices": status_choices,
        "monthly_summary": monthly_summary,
    }

    return render(request, "carwash/ticket_list_create.html", context)

@login_required
def get_customer_email(request):
    """AJAX endpoint to get existing customer emails for autocomplete in carwash"""
    user = request.user
    
    # Get emails from ServiceTicket model for carwash
    service_ticket_emails = ServiceTicket.objects.filter(
        created_by=user,
        customer_email__isnull=False
    ).exclude(customer_email='').values(
        'customer_email', 
        'car_number_plate'
    ).distinct()
    
    # Combine and deduplicate
    all_emails = {}
    for item in service_ticket_emails:
        if item['customer_email']:
            # For carwash, we might not have customer names, so we'll use email as identifier
            all_emails[item['customer_email']] = {
                'email': item['customer_email'],
                'name': '',  # Carwash might not collect names
                'car_plate': item['car_number_plate']
            }
    
    # Convert to list
    emails_list = list(all_emails.values())
    
    return JsonResponse({
        'emails': emails_list
    })

@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(ServiceTicket, pk=pk)
    return render(request, 'carwash/ticket_detail.html', {'ticket': ticket})

@login_required
def ticket_update_delete(request, pk):
    ticket = get_object_or_404(ServiceTicket, pk=pk, created_by=request.user)
    
    # Handle delete request (soft delete by changing status)
    if request.method == 'POST' and 'delete' in request.POST:
        ticket_number = ticket.ticket_number
        ticket.status = 'cancelled'
        ticket.save()
        messages.success(request, f'Ticket {ticket_number} cancelled successfully!')
        return redirect('ticket_list_create')
    
    # Handle update request
    if request.method == 'POST':
        form = ServiceTicketUpdateForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save()
            messages.success(request, f'Ticket {ticket.ticket_number} updated successfully!')
            return redirect('ticket_detail', pk=ticket.pk)
    else:
        form = ServiceTicketUpdateForm(instance=ticket)
    
    context = {
        'form': form,
        'ticket': ticket,
        'title': 'Update/Delete Ticket'
    }
    return render(request, 'carwash/ticket_update_delete.html', context)

# Revenue and Reports
@login_required
@company_category_required('car_wash')
def revenue_report(request):
    # Base queryset - filter by current user
    tickets = ServiceTicket.objects.filter(
        status='completed', 
        created_by=request.user
    ).select_related('service', 'employee')

    # Optional date filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        tickets = tickets.filter(completed_at__date__gte=date_from)
    if date_to:
        tickets = tickets.filter(completed_at__date__lte=date_to)

    # --- Monthly totals ---
    monthly_stats = (
        tickets.annotate(month=TruncMonth('completed_at'))
        .values('month')
        .annotate(
            total_revenue=Sum('total_amount'),
            total_cars=Count('id')
        )
        .order_by('-month')
    )

    # --- Revenue by service, grouped by month ---
    service_revenue = (
        tickets.annotate(month=TruncMonth('completed_at'))
        .values('month', 'service__name')
        .annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        )
        .order_by('-month', '-revenue')
    )

    # --- Revenue by employee, grouped by month ---
    employee_revenue = (
        tickets.annotate(month=TruncMonth('completed_at'))
        .values('month', 'employee__name', 'employee__surname')
        .annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        )
        .order_by('-month', '-revenue')
    )

    # Calculate overall totals for display
    overall_revenue = tickets.aggregate(total=Sum('total_amount'))['total'] or 0
    overall_cars = tickets.count()

    context = {
        'monthly_stats': monthly_stats,
        'service_revenue': service_revenue,
        'employee_revenue': employee_revenue,
        'date_from': date_from,
        'date_to': date_to,
        'overall_revenue': overall_revenue,
        'overall_cars': overall_cars,
    }
    return render(request, 'carwash/revenue_report.html', context)


# AI Chatbot Integration

@csrf_exempt
@require_POST
def carwash_ai_chat_endpoint(request):
    """AI chat endpoint for carwash business"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        logger.info(f"Carwash AI Chat request from user {request.user.username}: {user_message}")
        
        # Get carwash-specific data
        carwash_data = get_carwash_business_data(request.user)
        logger.info(f"Carwash data retrieved successfully for user {request.user.username}")
        
        # Generate AI response using carwash data
        ai_response = generate_carwash_ai_response(user_message, carwash_data)
        logger.info(f"AI response generated successfully")
        
        return JsonResponse({
            'success': True,
            'response': ai_response
        })
        
    except Exception as e:
        logger.error(f"Error in carwash_ai_chat_endpoint: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)

def get_carwash_business_data(user):
    """Extract carwash-specific business data for the given user"""
    try:
        # Get all carwash data for this user
        employees = Employee.objects.filter(created_by=user, is_active=True)
        services = Service.objects.filter(created_by=user, is_active=True)
        tickets = ServiceTicket.objects.filter(created_by=user)
        
        # Current date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today.replace(day=1)
        
        # Basic metrics
        total_revenue = tickets.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        total_completed_tickets = tickets.filter(status='completed').count()
        total_pending_tickets = tickets.filter(status='pending').count()
        total_in_progress_tickets = tickets.filter(status='in_progress').count()
        total_cancelled_tickets = tickets.filter(status='cancelled').count()
        
        # Time-based analysis
        today_tickets = tickets.filter(created_at__date=today)
        today_revenue = today_tickets.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0
        
        week_tickets = tickets.filter(created_at__date__gte=week_ago)
        week_revenue = week_tickets.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0
        
        month_tickets = tickets.filter(created_at__date__gte=month_ago)
        month_revenue = month_tickets.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Service performance analysis
        service_performance = services.annotate(
            tickets_count=Count('tickets'),
            service_revenue=Sum('tickets__total_amount')
        ).order_by('-service_revenue')
        
        # Employee performance
        employee_performance = employees.annotate(
            completed_tickets=Count('tickets', filter=Q(tickets__status='completed')),
            employee_revenue=Sum('tickets__total_amount', filter=Q(tickets__status='completed'))
        ).order_by('-employee_revenue')
        
        # Popular services (top 3)
        popular_services = list(service_performance.filter(tickets_count__gt=0)[:3])
        
        # Calculate average ticket value
        avg_ticket_value = 0
        if total_completed_tickets > 0:
            avg_ticket_value = total_revenue / total_completed_tickets
        
        # Calculate completion rate
        completion_rate = 0
        total_tickets_count = tickets.count()
        if total_tickets_count > 0:
            completion_rate = (total_completed_tickets / total_tickets_count) * 100
        
        return {
            # Basic business metrics
            'total_employees': employees.count(),
            'total_services': services.count(),
            'total_revenue': float(total_revenue),
            'total_completed_tickets': total_completed_tickets,
            'total_pending_tickets': total_pending_tickets,
            'total_in_progress_tickets': total_in_progress_tickets,
            'total_cancelled_tickets': total_cancelled_tickets,
            'total_tickets_count': total_tickets_count,
            
            # Time-based performance
            'today': {
                'tickets': today_tickets.count(),
                'revenue': float(today_revenue)
            },
            'this_week': {
                'tickets': week_tickets.count(),
                'revenue': float(week_revenue)
            },
            'this_month': {
                'tickets': month_tickets.count(),
                'revenue': float(month_revenue)
            },
            
            # Service analysis
            'service_performance': [
                {
                    'name': service.name,
                    'price': float(service.price),
                    'tickets_count': service.tickets_count or 0,
                    'revenue': float(service.service_revenue or 0),
                }
                for service in popular_services
            ],
            
            # Employee analysis
            'employee_performance': [
                {
                    'name': employee.full_name,
                    'completed_tickets': employee.completed_tickets or 0,
                    'revenue_generated': float(employee.employee_revenue or 0),
                }
                for employee in employee_performance if employee.completed_tickets > 0
            ],
            
            # Business health metrics
            'avg_ticket_value': float(avg_ticket_value),
            'completion_rate': float(completion_rate),
            
            'user_business_name': f"{user.username}'s Carwash"
        }
        
    except Exception as e:
        logger.error(f"Error in get_carwash_business_data: {str(e)}")
        # Return minimal data to avoid complete failure
        return {
            'total_employees': 0,
            'total_services': 0,
            'total_revenue': 0,
            'total_completed_tickets': 0,
            'total_pending_tickets': 0,
            'total_in_progress_tickets': 0,
            'total_cancelled_tickets': 0,
            'total_tickets_count': 0,
            'today': {'tickets': 0, 'revenue': 0},
            'this_week': {'tickets': 0, 'revenue': 0},
            'this_month': {'tickets': 0, 'revenue': 0},
            'service_performance': [],
            'employee_performance': [],
            'avg_ticket_value': 0,
            'completion_rate': 0,
            'user_business_name': 'Your Carwash'
        }

def generate_carwash_ai_response(user_message, carwash_data):
    """Use OpenAI API to generate carwash-specific intelligent responses"""
    
    # Prepare carwash-specific context
    context = f"""
    CARWASH BUSINESS DATA:

    BUSINESS OVERVIEW:
    - Total Employees: {carwash_data['total_employees']}
    - Total Services: {carwash_data['total_services']}
    - Total Revenue: R{carwash_data['total_revenue']:,.2f}
    - Completed Washes: {carwash_data['total_completed_tickets']}
    - Pending Washes: {carwash_data['total_pending_tickets']}
    - In Progress Washes: {carwash_data['total_in_progress_tickets']}
    - Cancelled Washes: {carwash_data['total_cancelled_tickets']}
    - Completion Rate: {carwash_data['completion_rate']:.1f}%
    - Average Ticket Value: R{carwash_data['avg_ticket_value']:,.2f}

    TODAY'S PERFORMANCE:
    - Washes: {carwash_data['today']['tickets']}
    - Revenue: R{carwash_data['today']['revenue']:,.2f}

    THIS WEEK:
    - Washes: {carwash_data['this_week']['tickets']}
    - Revenue: R{carwash_data['this_week']['revenue']:,.2f}

    THIS MONTH:
    - Washes: {carwash_data['this_month']['tickets']}
    - Revenue: R{carwash_data['this_month']['revenue']:,.2f}

    TOP PERFORMING SERVICES:
    {chr(10).join([f"  - {service['name']}: {service['tickets_count']} washes (R{service['revenue']:,.2f})" for service in carwash_data['service_performance'][:3]])}

    EMPLOYEE PERFORMANCE:
    {chr(10).join([f"  - {employee['name']}: {employee['completed_tickets']} washes, R{employee['revenue_generated']:,.2f} revenue" for employee in carwash_data['employee_performance'][:3]])}

    USER QUESTION: {user_message}
    """
    
    # Carwash-specific system prompt
    system_prompt = """You are an intelligent carwash management assistant specializing in vehicle cleaning services.
    Provide helpful, professional responses about carwash operations, vehicle washes, and business performance.
    Use carwash terminology like 'washes', 'services', 'vehicles', 'employees' instead of generic business terms.
    Be concise and focus on the data provided."""
    
    try:
        # Check if OpenAI API key is available
        if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not found, using fallback response")
            return generate_carwash_fallback_response(user_message, carwash_data)
        
        # Try both OpenAI versions
        try:
            # Try new version first (v1.0+)
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                max_tokens=300,
                temperature=0.3
            )
            return response.choices[0].message.content
            
        except AttributeError:
            # Fall back to old version
            openai.api_key = settings.OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context}
                ],
                max_tokens=300,
                temperature=0.3
            )
            return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return generate_carwash_fallback_response(user_message, carwash_data)

def generate_carwash_fallback_response(user_message, carwash_data):
    """Fallback response when OpenAI is unavailable"""
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ['revenue', 'income', 'money']):
        return f"💰 Your carwash has generated R{carwash_data['total_revenue']:,.2f} in total revenue. This month: R{carwash_data['this_month']['revenue']:,.2f}"
    
    elif any(word in message_lower for word in ['wash', 'ticket', 'service', 'vehicle']):
        return f"🚗 You have {carwash_data['total_completed_tickets']} completed washes, {carwash_data['total_pending_tickets']} pending, and {carwash_data['total_in_progress_tickets']} in progress. Completion rate: {carwash_data['completion_rate']:.1f}%"
    
    elif any(word in message_lower for word in ['today']):
        return f"📊 Today: {carwash_data['today']['tickets']} washes, R{carwash_data['today']['revenue']:,.2f} revenue"
    
    elif any(word in message_lower for word in ['employee', 'worker', 'staff']):
        if carwash_data['employee_performance']:
            top_employee = carwash_data['employee_performance'][0]
            return f"👨‍💼 Your top employee is {top_employee['name']} with {top_employee['completed_tickets']} washes and R{top_employee['revenue_generated']:,.2f} revenue"
        else:
            return f"👨‍💼 You have {carwash_data['total_employees']} employees working at your carwash."
    
    elif any(word in message_lower for word in ['service', 'package']):
        if carwash_data['service_performance']:
            top_service = carwash_data['service_performance'][0]
            return f"🧼 Most popular service: {top_service['name']} with {top_service['tickets_count']} washes (R{top_service['revenue']:,.2f})"
        else:
            return f"🧼 You offer {carwash_data['total_services']} different services at your carwash."
    
    else:
        return f"🚗 Carwash Overview: {carwash_data['total_services']} services, {carwash_data['total_employees']} employees, R{carwash_data['total_revenue']:,.2f} total revenue. Ask me about washes, revenue, or employee performance!"


