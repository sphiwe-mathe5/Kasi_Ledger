# salon/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, Avg, Max, F
from django.db.models.functions import TruncMonth, Coalesce
from django.utils import timezone
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models.functions import TruncMonth
from .models import Worker, Style, StyleTicket, SalonProfile, WorkingHours, Booking, Review, AvailabilitySlot, RecurringAvailability
from .forms import WorkerForm, StyleForm, StyleTicketForm
from datetime import datetime, timedelta
from calendar import monthrange, monthcalendar
from django.utils.timezone import now
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
import openai
import json
from datetime import date
from .decorators import subscription_required
from .subscriptions import get_user_subscription_status, check_feature_access
from submit.models import Subscription
from .decorators import company_category_required
from django.db.models import ExpressionWrapper, DecimalField, IntegerField




import logging
logger = logging.getLogger(__name__)

def guides(request):
    return render(request, 'saloon/guides.html')

@login_required
#@subscription_required()
@company_category_required('salon')
def saloon(request):
    """Salon dashboard with updated subscription logic"""
    user = request.user
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    # Get subscription status
    sub_status = get_user_subscription_status(user)
    
    # --- BASE QUERIES ---
    workers = Worker.objects.filter(created_by=user)
    styles = Style.objects.filter(created_by=user)

    # --- TOTAL REVENUE ---
    total_style_revenue = StyleTicket.objects.filter(
        created_by=user, completed=True
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    total_booking_revenue = Booking.objects.filter(
        salon__user=user, status='completed'
    ).aggregate(total=Sum('price'))['total'] or 0

    total_revenue = total_style_revenue + total_booking_revenue

    # --- TOTAL COUNTS ---
    total_styles = StyleTicket.objects.filter(created_by=user, completed=True).count()
    active_workers = workers.count()

    total_tickets = (
        StyleTicket.objects.filter(created_by=user).count()
        + Booking.objects.filter(salon__user=user, status='completed').count()
    )

    # --- TODAY'S STATS ---
    today_tickets = StyleTicket.objects.filter(
        created_by=user, created_at__date=today
    )

    today_bookings = Booking.objects.filter(
        salon__user=user, 
        completed_at__date=today,
        status='completed'
    )

    today_tickets_count = today_tickets.count() + today_bookings.count()

    today_style_revenue = today_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
    today_booking_revenue = today_bookings.aggregate(total=Sum('price'))['total'] or 0
    today_revenue = today_style_revenue + today_booking_revenue

    # --- THIS MONTH'S STATS ---
    month_tickets = StyleTicket.objects.filter(
        created_by=user, created_at__date__gte=start_of_month
    )
    month_bookings = Booking.objects.filter(
        salon__user=user, booking_date__gte=start_of_month, status='completed'
    )

    month_tickets_count = month_tickets.count() + month_bookings.count()

    month_style_revenue = month_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
    month_booking_revenue = month_bookings.aggregate(total=Sum('price'))['total'] or 0
    month_revenue = month_style_revenue + month_booking_revenue

    # --- RECENT TRANSACTIONS ---
    recent_tickets = StyleTicket.objects.filter(
        created_by=user
    ).select_related('style', 'worker').order_by('-created_at')[:5]

    recent_bookings = Booking.objects.filter(
        salon__user=user, status='completed'
    ).select_related('style', 'worker').order_by('-completed_at')[:5]

    recent_transactions = []
    
    for ticket in recent_tickets:
        recent_transactions.append({
            'type': 'ticket',
            'object': ticket,
            'date': ticket.created_at,
            'customer_name': ticket.customer_name,
            'service': ticket.style.name,
            'worker': ticket.worker,
            'amount': ticket.total_amount,
            'status': 'Completed' if ticket.completed else 'Pending'
        })
    
    for booking in recent_bookings:
        recent_transactions.append({
            'type': 'booking',
            'object': booking,
            'date': booking.completed_at or booking.created_at,
            'customer_name': booking.customer_name,
            'service': booking.style.name,
            'worker': booking.worker,
            'amount': booking.price,
            'status': booking.get_status_display()
        })
    
    recent_transactions.sort(key=lambda x: x['date'], reverse=True)
    recent_transactions = recent_transactions[:5]

    # --- WORKER PERFORMANCE ---
    worker_stats = []
    for worker in Worker.objects.filter(created_by=user):
        style_tickets = worker.style_tickets.filter(
            created_at__date__gte=start_of_month,
            created_by=user,
        )
        styles_completed = style_tickets.count()
        style_revenue = style_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
        
        bookings = worker.bookings.filter(
            booking_date__gte=start_of_month,
            salon__user=user,
            status='completed'
        )
        bookings_completed = bookings.count()
        booking_revenue = bookings.aggregate(total=Sum('price'))['total'] or 0
        
        total_appointments = styles_completed + bookings_completed
        total_revenue = style_revenue + booking_revenue
        
        if total_appointments > 0:
            worker_stats.append({
                'worker': worker,
                'styles_completed': styles_completed,
                'bookings_completed': bookings_completed,
                'total_appointments': total_appointments,
                'total_revenue': total_revenue
            })
    
    worker_stats.sort(key=lambda x: x['total_revenue'], reverse=True)
    worker_stats = worker_stats[:5]

    # --- PAGINATION ---
    paginator = Paginator(styles, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- CHECK FEATURE ACCESS ---
    chatbot_access = check_feature_access(user, 'chatbot')
    appointments_access = check_feature_access(user, 'appointments')
    
    # Show trial warning if applicable
    show_trial_warning = sub_status['is_trialing'] and not sub_status['trial_expired']

    # --- CONTEXT ---
    context = {
        'page_obj': page_obj,
        'workers': workers,
        'styles': styles,
        'total_revenue': total_revenue,
        'total_styles': total_styles,
        'styless': styles.count(),
        'total_tickets': total_tickets,
        'active_workers': active_workers,
        'today_tickets_count': today_tickets_count,
        'today_revenue': today_revenue,
        'month_tickets_count': month_tickets_count,
        'month_revenue': month_revenue,
        'recent_transactions': recent_transactions,
        'worker_stats': worker_stats,
        'pending_tickets': StyleTicket.objects.filter(created_by=user, completed=False).count(),
        'pending_bookings': Booking.objects.filter(salon__user=user, status='pending').count(),
        
        # Subscription context
        'subscription': sub_status,
        'current_plan': sub_status['display_plan'],
        'is_trialing': sub_status['is_trialing'],
        'trial_days_left': sub_status['days_left'],
        'show_trial_warning': show_trial_warning,
        'show_ai_chatbot': chatbot_access['allowed'],
        'appointments_remaining': appointments_access.get('limit') and (
            appointments_access['limit'] - appointments_access['current']
        ),
        'current_time': timezone.now(),
    }

    return render(request, 'saloon/saloon-dashboard.html', context)


@login_required
@company_category_required('salon')
def worker_list_create(request):
    # Handle form submission
    if request.method == 'POST':
        form = WorkerForm(request.POST)
        if form.is_valid():
            worker = form.save(commit=False)
            worker.created_by = request.user
            worker.save()
            messages.success(request, f'Hair Stylist {worker.name} {worker.surname} created successfully!')
            return redirect('saloon:worker_list_create')
    else:
        form = WorkerForm()

    # Handle search and listing
    search_query = request.GET.get('search', '')
    workers = Worker.objects.filter(created_by=request.user)
    
    if search_query:
        workers = workers.filter(
            Q(name__icontains=search_query) |
            Q(surname__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Calculate stats including both StyleTickets and Bookings
    for worker in workers:
        # StyleTicket stats (completed only)
        style_tickets = worker.style_tickets.filter(
            created_by=request.user,
        )
        styles_completed = style_tickets.count()
        style_revenue = style_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Booking stats (completed only)
        bookings = worker.bookings.filter(
            salon__user=request.user,
            status='completed'
        )
        bookings_completed = bookings.count()
        booking_revenue = bookings.aggregate(total=Sum('price'))['total'] or 0
        
        # Total stats
        worker.total_styles = styles_completed + bookings_completed
        worker.total_revenue = style_revenue + booking_revenue
    
    paginator = Paginator(workers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'saloon/worker_list_create.html', context)

@login_required
def worker_update(request, pk):
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == 'POST':
        form = WorkerForm(request.POST, instance=worker)
        if form.is_valid():
            form.save()
            messages.success(request, f'Hair Stylist {worker.name} {worker.surname} updated successfully!')
        else:
            messages.error(request, "Error updating worker.")
        return redirect('saloon:worker_list_create')

@login_required
def worker_delete(request, pk):
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == "POST":
        worker.delete()
        messages.success(request, f"Hair Stylist {worker.name} {worker.surname} deleted successfully!")
        return redirect('saloon:worker_list_create')

    messages.error(request, "Invalid request.")
    return redirect('saloon:worker_list_create')


@login_required
@company_category_required('salon')
def style_list(request):
    styles = Style.objects.filter(created_by=request.user)

    return render(request, 'saloon/style_list.html', {'styles': styles})

@login_required
@company_category_required('salon')
def style_create(request):
    if request.method == 'POST':
        form = StyleForm(request.POST)
        if form.is_valid():
            style = form.save(commit=False)
            style.created_by = request.user
            style.save()
            messages.success(request, f'Hair Style {style.name} created successfully!')
            return redirect('saloon:saloon')
    else:
        form = StyleForm()
    return render(request, 'saloon/style_form.html', {'form': form, 'title': 'Add Style'})

@login_required
def style_edit(request, pk):
    style = get_object_or_404(Style, pk=pk)
    if request.method == 'POST':
        form = StyleForm(request.POST, instance=style)
        if form.is_valid():
            form.save()
            messages.success(request, f'Style {style.name} updated successfully!')
            return redirect('style_list')
    else:
        form = StyleForm(instance=style)
    return render(request, 'saloon/style_form.html', {'form': form, 'title': 'Edit Style'})




@login_required
@company_category_required('salon')
def ticket_create(request):
    if request.method == 'POST':
        form = StyleTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            ticket.save()

            if ticket.customer_email and not ticket.created_by.email:
                user = ticket.created_by
                user.email = ticket.customer_email
                user.save()

            ticket.save()

            # ✅ Send receipt email if customer email is provided
            if ticket.customer_email:
                subject = f"Your Style Ticket #{ticket.ticket_number}"
                from_email = settings.DEFAULT_FROM_EMAIL
                to_email = [ticket.customer_email]

                # Context for the email template
                html_content = render_to_string("saloon/email_receipt.html", {
                    "ticket": ticket,
                    "company_name": ticket.created_by.company_name or "Our",
                })
                text_content = strip_tags(html_content)

                email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
                email.attach_alternative(html_content, "text/html")
                email.send()

            messages.success(request, f'Hair Style Appointment {ticket.ticket_number} created successfully!')
            return redirect('saloon:saloon')
    else:
        form = StyleTicketForm()

    search_query = request.GET.get('search', '')
    
    # Get both StyleTickets and Bookings
    style_tickets = StyleTicket.objects.select_related('style', 'worker').order_by('-created_at').filter(created_by=request.user)
    bookings = Booking.objects.select_related('style', 'worker', 'salon').order_by('-created_at').filter(salon__user=request.user, status='completed')

    # Combine both types of appointments
    all_appointments = []
    
    # Add StyleTickets
    for ticket in style_tickets:
        all_appointments.append({
            'type': 'ticket',
            'object': ticket,
            'id': ticket.id,
            'number': ticket.ticket_number,
            'customer_name': ticket.customer_name,
            'customer_phone': ticket.customer_phone,
            'customer_email': ticket.customer_email,
            'service': ticket.style.name,
            'worker': ticket.worker,
            'amount': ticket.total_amount,
            'created_at': ticket.created_at,
            'status': 'Completed' if ticket.completed else 'Pending'
        })
    
    # Add Bookings
    for booking in bookings:
        all_appointments.append({
            'type': 'booking',
            'object': booking,
            'id': booking.id,
            'number': booking.booking_number,
            'customer_name': booking.customer_name,
            'customer_phone': booking.customer_phone,
            'customer_email': booking.customer_email,
            'service': booking.style.name,
            'worker': booking.worker,
            'amount': booking.price,
            'created_at': booking.created_at,
            'status': booking.get_status_display(),
            'booking_date': booking.booking_date,
            'booking_time': booking.booking_time
        })
    
    # Sort combined appointments by creation date (most recent first)
    all_appointments.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Apply search filter if provided
    if search_query:
        filtered_appointments = []
        for appointment in all_appointments:
            if (search_query.lower() in appointment['number'].lower() or
                search_query.lower() in appointment['customer_name'].lower() or
                search_query.lower() in (appointment['customer_email'] or '').lower() or
                search_query.lower() in (appointment['customer_phone'] or '').lower()):
                filtered_appointments.append(appointment)
        all_appointments = filtered_appointments

    total_tickets = len(all_appointments)

    # Pagination
    paginator = Paginator(all_appointments, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Monthly summary (StyleTickets only for now)
    monthly_summary = (
        StyleTicket.objects.filter(completed=True).filter(created_by=request.user)
        .annotate(month=TruncMonth("completed_at"))
        .values("month")
        .annotate(total_revenue=Sum("total_amount"), count=Count("id"))
        .order_by("-month")
    )

    context = {
        'form': form,
        'page_obj': page_obj,
        'search_query': search_query,
        'monthly_summary': monthly_summary,
        'total_tickets': total_tickets,
    }
    return render(request, 'saloon/ticket_list.html', context)


@login_required
@company_category_required('salon')
def salon_report(request):
    user = request.user
    
    # --- MONTHLY STATS - COMBINED STYLETICKETS AND BOOKINGS ---
    # StyleTicket monthly stats (all tickets)
    style_monthly_stats = (
        StyleTicket.objects.filter(created_by=user)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            total_revenue=Sum('total_amount'),
            total_appointments=Count('id')
        )
    )
    
    # Booking monthly stats (only completed)
    booking_monthly_stats = (
        Booking.objects.filter(salon__user=user, status='completed')
        .annotate(month=TruncMonth('completed_at'))
        .values('month')
        .annotate(
            total_revenue=Sum('price'),
            total_appointments=Count('id')
        )
    )
    
    # Combine monthly stats
    monthly_stats_dict = {}
    
    # Add StyleTicket stats
    for stat in style_monthly_stats:
        month = stat['month']
        if month not in monthly_stats_dict:
            monthly_stats_dict[month] = {
                'month': month,
                'total_revenue': 0,
                'total_appointments': 0
            }
        monthly_stats_dict[month]['total_revenue'] += stat['total_revenue'] or 0
        monthly_stats_dict[month]['total_appointments'] += stat['total_appointments'] or 0
    
    # Add Booking stats (only completed)
    for stat in booking_monthly_stats:
        month = stat['month']
        if month not in monthly_stats_dict:
            monthly_stats_dict[month] = {
                'month': month,
                'total_revenue': 0,
                'total_appointments': 0
            }
        monthly_stats_dict[month]['total_revenue'] += stat['total_revenue'] or 0
        monthly_stats_dict[month]['total_appointments'] += stat['total_appointments'] or 0
    
    # Convert to list and sort by month (descending)
    monthly_stats = sorted(monthly_stats_dict.values(), key=lambda x: x['month'], reverse=True)

    # --- REVENUE BY WORKER - COMBINED ---
    # StyleTicket revenue by worker (all tickets)
    style_revenue_by_worker = (
        StyleTicket.objects.filter(created_by=user)
        .annotate(month=TruncMonth('created_at'))
        .values('month', 'worker__name', 'worker__surname')
        .annotate(total_revenue=Sum('total_amount'))
        .order_by('-month', '-total_revenue')
    )
    
    # Booking revenue by worker (only completed)
    booking_revenue_by_worker = (
        Booking.objects.filter(salon__user=user, status='completed')
        .annotate(month=TruncMonth('completed_at'))
        .values('month', 'worker__name', 'worker__surname')
        .annotate(total_revenue=Sum('price'))
        .order_by('-month', '-total_revenue')
    )
    
    # Combine worker revenue
    revenue_by_worker = []
    for stat in style_revenue_by_worker:
        revenue_by_worker.append({
            'month': stat['month'],
            'worker__name': f"{stat['worker__name']} {stat['worker__surname']}",
            'total_revenue': stat['total_revenue'] or 0
        })
    
    for stat in booking_revenue_by_worker:
        worker_name = f"{stat['worker__name']} {stat['worker__surname']}" if stat['worker__name'] else "No Stylist"
        revenue_by_worker.append({
            'month': stat['month'],
            'worker__name': worker_name,
            'total_revenue': stat['total_revenue'] or 0
        })
    
    # Sort worker revenue by month and revenue
    revenue_by_worker.sort(key=lambda x: (x['month'], x['total_revenue']), reverse=True)

    # --- REVENUE BY STYLE - COMBINED ---
    # StyleTicket revenue by style (all tickets)
    style_revenue_by_style = (
        StyleTicket.objects.filter(created_by=user)
        .annotate(month=TruncMonth('created_at'))
        .values('month', 'style__name')
        .annotate(total_revenue=Sum('total_amount'))
        .order_by('-month', '-total_revenue')
    )
    
    # Booking revenue by style (only completed)
    booking_revenue_by_style = (
        Booking.objects.filter(salon__user=user, status='completed')
        .annotate(month=TruncMonth('completed_at'))
        .values('month', 'style__name')
        .annotate(total_revenue=Sum('price'))
        .order_by('-month', '-total_revenue')
    )
    
    # Combine style revenue
    revenue_by_style = []
    for stat in style_revenue_by_style:
        revenue_by_style.append({
            'month': stat['month'],
            'style__name': stat['style__name'],
            'total_revenue': stat['total_revenue'] or 0
        })
    
    for stat in booking_revenue_by_style:
        revenue_by_style.append({
            'month': stat['month'],
            'style__name': stat['style__name'],
            'total_revenue': stat['total_revenue'] or 0
        })
    
    # Sort style revenue by month and revenue
    revenue_by_style.sort(key=lambda x: (x['month'], x['total_revenue']), reverse=True)

    context = {
        'monthly_stats': monthly_stats,
        'revenue_by_style': revenue_by_style,
        'revenue_by_worker': revenue_by_worker,
    }
    
    return render(request, 'saloon/salon_report.html', context)


@login_required
@company_category_required('salon')
def create_salon_profile(request):
    """Create or update salon profile - Page 1"""
    
    # Get or create salon profile
    profile, created = SalonProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update profile fields
        profile.bio = request.POST.get('bio', '')
        profile.address = request.POST.get('address', '')
        profile.city = request.POST.get('city', '')
        profile.whatsapp_number = request.POST.get('whatsapp_number', '')
        profile.facebook_url = request.POST.get('facebook_url', '')
        profile.instagram_url = request.POST.get('instagram_url', '')
        profile.save()
        
        # Update working hours
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_mapping = {
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5,
            'sunday': 6
        }
        
        for day in days:
            is_open = request.POST.get(f'{day}_open')
            opening_time = request.POST.get(f'{day}_opening')
            closing_time = request.POST.get(f'{day}_closing')
            
            if is_open and opening_time and closing_time:
                WorkingHours.objects.update_or_create(
                    salon=profile,
                    day_of_week=day_mapping[day],
                    defaults={
                        'opening_time': opening_time,
                        'closing_time': closing_time,
                        'is_closed': False
                    }
                )
            else:
                # Mark as closed
                WorkingHours.objects.filter(
                    salon=profile,
                    day_of_week=day_mapping[day]
                ).delete()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('saloon:salon_profile', slug=profile.slug)
    
    # Get working hours for display
    working_hours_list = WorkingHours.objects.filter(salon=profile, is_closed=False)
    working_hours_dict = {}
    day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    for hours in working_hours_list:
        working_hours_dict[day_names[hours.day_of_week]] = hours
    
    context = {
        'profile': profile,
        'working_hours': working_hours_dict,
    }
    
    return render(request, 'saloon/profile_setup.html', context)

def check_owner_subscription(user):
    """Check if owner has paid subscription to view bookings"""
    try:
        subscription = Subscription.objects.get(user=user)
        now = timezone.now()
        
        # Check if subscription is active
        if subscription.status == 'trialing':
            if subscription.trial_end_date <= now:
                return False, 'Trial expired'
        elif subscription.status == 'active':
            if subscription.next_payment_date and subscription.next_payment_date <= now:
                return False, 'Subscription expired'
        
        # Only Business Pro can see bookings
        if subscription.plan.name != 'Business Pro':
            return False, 'Business Pro only'
        
        return True, 'Active'
    
    except Subscription.DoesNotExist:
        return False, 'No subscription'


def check_public_booking_allowed(profile):
    """Check if the SALON OWNER has subscription allowing public bookings"""
    try:
        subscription = Subscription.objects.get(user=profile.user)
        
        # Check subscription status
        sub_status = get_user_subscription_status(profile.user)
        
        if not sub_status['is_active']:
            return False, 'Salon subscription is not active'
        
        # Check if plan allows public bookings
        booking_check = check_feature_access(profile.user, 'bookings_create')
        
        if not booking_check['allowed']:
            return False, booking_check['message']
        
        return True, 'Bookings allowed'
    
    except Subscription.DoesNotExist:
        return False, 'Salon owner has no active subscription'


@login_required
def manage_availability(request):
    """
    Salon owner can view and manage their availability slots AND bookings
    """
    user = request.user
    
    # Get salon profile
    try:
        salon = SalonProfile.objects.get(user=user)
    except SalonProfile.DoesNotExist:
        messages.error(request, 'Please create a salon profile first.')
        return redirect('saloon:dashboard')
    
    # ✅ Check subscription access for bookings management
    bookings_access = check_feature_access(user, 'bookings_view')
    if not bookings_access['allowed']:
        messages.error(request, bookings_access['message'])
        # Still show the page but with limited functionality
    
    # Get workers
    workers = Worker.objects.filter(created_by=user)
    
    # Get date range for display (next 30 days)
    today = date.today()
    end_date = today + timedelta(days=30)
    
    # Get all availability slots
    slots = AvailabilitySlot.objects.filter(
        salon=salon,
        date__range=[today, end_date]
    ).select_related('worker', 'booking')
    
    # Get recurring availability rules
    recurring_rules = RecurringAvailability.objects.filter(
        salon=salon,
        is_active=True
    ).select_related('worker')
    
    # ✅ NEW: Get bookings data (only if user has access)
    bookings = []
    booking_stats = {}
    
    if bookings_access['allowed']:
        # Get recent bookings
        bookings = Booking.objects.filter(
            salon=salon
        ).select_related('style', 'worker').order_by('-booking_date', '-booking_time')[:20]
        
        # Get booking statistics
        booking_stats = Booking.objects.filter(salon=salon).aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            confirmed=Count('id', filter=Q(status='confirmed')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            total_revenue=Sum('price', filter=Q(status='completed'))
        )
    
    context = {
        'salon': salon,
        'workers': workers,
        'slots': slots,
        'recurring_rules': recurring_rules,
        'today': today.isoformat(),
        'end_date': end_date.isoformat(),
        
        # ✅ NEW: Bookings management context
        'can_view_bookings': bookings_access['allowed'],
        'booking_restriction_reason': bookings_access['message'],
        'bookings': bookings,
        'total_bookings': booking_stats.get('total', 0) or 0,
        'pending_bookings': booking_stats.get('pending', 0) or 0,
        'confirmed_bookings': booking_stats.get('confirmed', 0) or 0,
        'completed_bookings': booking_stats.get('completed', 0) or 0,
        'cancelled_bookings': booking_stats.get('cancelled', 0) or 0,
        'total_revenue': booking_stats.get('total_revenue', 0) or 0,
    }
    
    return render(request, 'saloon/manage_availability.html', context)


@login_required
@require_http_methods(["POST"])
def create_availability_slot(request):
    """Create a single availability slot"""
    user = request.user
    
    try:
        salon = SalonProfile.objects.get(user=user)
    except SalonProfile.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Salon profile not found'}, status=404)
    
    try:
        data = json.loads(request.body)
        
        worker_id = data.get('worker_id')
        date_str = data.get('date')
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        duration = int(data.get('duration_minutes', 60))
        
        # Parse date and times
        slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Validate date is not in past
        if slot_date < date.today():
            return JsonResponse({'success': False, 'message': 'Cannot create slots for past dates'}, status=400)
        
        # Get worker if specified
        worker = None
        if worker_id:
            worker = Worker.objects.get(id=worker_id, created_by=user)
        
        # ✅ CHECK FOR DUPLICATE SLOTS
        # Check if slot already exists for this salon, date, time, and worker
        duplicate_slot = AvailabilitySlot.objects.filter(
            salon=salon,
            worker=worker,  # This handles both None (any worker) and specific worker
            date=slot_date,
            start_time=start_time
        ).exists()
        
        if duplicate_slot:
            worker_name = worker.full_name if worker else "Any Worker"
            return JsonResponse({
                'success': False, 
                'message': f'A slot already exists for {slot_date} at {start_time_str} for {worker_name}. Please choose a different time or delete the existing slot first.',
                'reason': 'duplicate'
            }, status=400)
        
        # Create slot
        slot = AvailabilitySlot.objects.create(
            salon=salon,
            worker=worker,
            date=slot_date,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            created_by=user
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Availability slot created successfully',
            'slot': {
                'id': slot.id,
                'date': slot.date.isoformat(),
                'start_time': slot.start_time.strftime('%H:%M'),
                'end_time': slot.end_time.strftime('%H:%M'),
                'is_available': slot.is_available
            }
        })
        
    except Worker.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Worker not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def create_recurring_availability(request):
    """Create recurring availability pattern"""
    user = request.user
    
    try:
        salon = SalonProfile.objects.get(user=user)
    except SalonProfile.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Salon profile not found'}, status=404)
    
    try:
        data = json.loads(request.body)
        
        worker_id = data.get('worker_id')
        weekday = int(data.get('weekday'))
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        slot_duration = int(data.get('slot_duration_minutes', 60))
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        
        # Parse times and dates
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        # Get worker if specified
        worker = None
        if worker_id:
            worker = Worker.objects.get(id=worker_id, created_by=user)
        
        # Create recurring rule
        recurring = RecurringAvailability.objects.create(
            salon=salon,
            worker=worker,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            slot_duration_minutes=slot_duration,
            start_date=start_date,
            end_date=end_date,
            created_by=user
        )
        
        # Generate slots for next 30 days
        generation_end = min(end_date, date.today() + timedelta(days=30)) if end_date else date.today() + timedelta(days=30)
        slots_created = recurring.generate_slots_for_date_range(start_date, generation_end)
        
        return JsonResponse({
            'success': True,
            'message': f'Recurring availability created. Generated {slots_created} slots.',
            'recurring_id': recurring.id,
            'slots_created': slots_created
        })
        
    except Worker.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Worker not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def delete_availability_slot(request, slot_id):
    """Delete a single availability slot (only if not booked)"""
    user = request.user
    
    try:
        slot = AvailabilitySlot.objects.get(id=slot_id, created_by=user)
        
        if slot.is_booked:
            return JsonResponse({
                'success': False,
                'message': 'Cannot delete a booked slot. Cancel the booking first.'
            }, status=400)
        
        slot.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Availability slot deleted successfully'
        })
        
    except AvailabilitySlot.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Slot not found'}, status=404)


def get_available_slots(request, slug):
    """
    API endpoint for customers to fetch available slots
    Used by the booking form to show only available times
    """
    profile = get_object_or_404(SalonProfile, slug=slug, is_active=True)
    
    date_str = request.GET.get('date')
    worker_id = request.GET.get('worker_id')
    
    if not date_str:
        return JsonResponse({'success': False, 'message': 'Date is required'}, status=400)
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid date format'}, status=400)
    
    # Build query
    query = Q(salon=profile, date=selected_date, is_booked=False)
    
    if worker_id:
        query &= Q(worker_id=worker_id)
    
    # Get available slots
    available_slots = AvailabilitySlot.objects.filter(query).order_by('start_time')
    
    slots_data = [{
        'id': slot.id,
        'start_time': slot.start_time.strftime('%H:%M'),
        'end_time': slot.end_time.strftime('%H:%M'),
        'worker_id': slot.worker.id if slot.worker else None,
        'worker_name': slot.worker.full_name if slot.worker else 'Any Worker'
    } for slot in available_slots]
    
    return JsonResponse({
        'success': True,
        'date': selected_date.isoformat(),
        'slots': slots_data
    })


def salon_profile(request, slug):
    """
    Public salon profile view - ANYONE can view (no login required)
    - Customers see: services, reviews, booking form
    - Owner sees: dashboard, bookings (if plan allows)
    """
    profile = get_object_or_404(SalonProfile, slug=slug, is_active=True)
    
    # Check if current user is the owner (requires login)
    is_owner = request.user.is_authenticated and request.user == profile.user

    booking_allowed, booking_message = check_public_booking_allowed(profile)
    
    # Get working hours
    working_hours_list = WorkingHours.objects.filter(salon=profile, is_closed=False)
    
    # Get services
    if is_owner:
        # Owner sees all their styles
        styles = Style.objects.filter(created_by=request.user)
    else:
        # Public only sees active styles
        styles = Style.objects.filter(created_by=profile.user, is_active=True)
    
    # Get workers
    workers = Worker.objects.filter(created_by=profile.user)
    
    # Get available dates (next 30 days with available slots)
    today = date.today()
    end_date = today + timedelta(days=30)
    
    # Get all available slots grouped by date
    available_slots = AvailabilitySlot.objects.filter(
        salon=profile,
        date__range=[today, end_date],
        is_booked=False
    ).select_related('worker').order_by('date', 'start_time')
    
    # Group slots by date for easy access in template
    from itertools import groupby
    from operator import attrgetter
    
    slots_by_date = {}
    for date_key, slots_group in groupby(available_slots, key=attrgetter('date')):
        slots_by_date[date_key.isoformat()] = [
            {
                'id': slot.id,
                'start_time': slot.start_time.strftime('%H:%M'),
                'end_time': slot.end_time.strftime('%H:%M'),
                'worker_id': slot.worker.id if slot.worker else None,
                'worker_name': slot.worker.full_name if slot.worker else 'Any Worker'
            }
            for slot in slots_group
        ]
    
    # Convert to JSON for JavaScript
    import json
    slots_json = json.dumps(slots_by_date)
    
    # Base context
    context = {
        'is_owner': is_owner,
        'profile': profile,
        'working_hours_list': working_hours_list,
        'styles': styles,
        'workers': workers,
        'today': today.isoformat(),
        'booking_allowed': booking_allowed,
        'slots_by_date': slots_json,  # Add this
    }
    
    # ===== OWNER-SPECIFIC DATA (requires login & subscription check) =====
    if is_owner:
        # Owner is viewing their own salon - check their subscription
        bookings_access = check_feature_access(request.user, 'bookings_view')
        context['can_view_bookings'] = bookings_access['allowed']
        context['booking_restriction_reason'] = bookings_access['message']
        
        if bookings_access['allowed']:
            # Owner has permission to view bookings
            bookings = Booking.objects.filter(
                salon=profile
            ).order_by('-booking_date', '-booking_time')[:20]
            
            booking_stats = Booking.objects.filter(salon=profile).aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='pending')),
                confirmed=Count('id', filter=Q(status='confirmed')),
                completed=Count('id', filter=Q(status='completed')),
                cancelled=Count('id', filter=Q(status='cancelled')),
                total_revenue=Sum('price', filter=Q(status='completed'))
            )
            
            context.update({
                'bookings': bookings,
                'total_bookings': booking_stats['total'] or 0,
                'pending_bookings': booking_stats['pending'] or 0,
                'confirmed_bookings': booking_stats['confirmed'] or 0,
                'completed_bookings': booking_stats['completed'] or 0,
                'cancelled_bookings': booking_stats['cancelled'] or 0,
                'total_revenue': booking_stats['total_revenue'] or 0,
            })
        else:
            # Owner without permission - show upgrade notice
            context.update({'bookings': [], 'total_bookings': 0})
    
    # ===== PUBLIC/CUSTOMER DATA (no login required) =====
    else:
        # Check if salon allows public bookings (based on OWNER'S subscription)
        booking_allowed, booking_reason = check_public_booking_allowed(profile)
        context['booking_allowed'] = booking_allowed
        context['booking_disabled_reason'] = booking_reason
        
        # Show reviews (public)
        reviews = Review.objects.filter(salon=profile).order_by('-created_at')[:10]
        context['reviews'] = reviews
    
    return render(request, 'saloon/salon-profile.html', context)

@require_http_methods(["POST"])
def create_booking(request, slug):
    """
    Updated: Create booking from available slot
    """
    profile = get_object_or_404(SalonProfile, slug=slug, is_active=True)
    
    # Check if salon owner's subscription allows public bookings
    booking_allowed, booking_reason = check_public_booking_allowed(profile)
    
    if not booking_allowed:
        messages.error(
            request, 
            f'Bookings are currently unavailable: {booking_reason}. Please contact the salon directly.'
        )
        return redirect('saloon:salon_profile', slug=slug)
    
    # Extract form data
    customer_name = request.POST.get('customer_name', '').strip()
    customer_phone = request.POST.get('customer_phone', '').strip()
    customer_email = request.POST.get('customer_email', '').strip()
    style_id = request.POST.get('style')
    slot_id = request.POST.get('slot_id')  # NEW: Get slot ID instead of manual time
    customer_notes = request.POST.get('customer_notes', '').strip()
    
    # Validate required fields
    if not all([customer_name, customer_phone, customer_email, style_id, slot_id]):
        messages.error(request, 'Please fill in all required fields and select a time slot.')
        return redirect('saloon:salon_profile', slug=slug)
    
    try:
        # Get and validate style
        style = Style.objects.get(
            id=style_id, 
            is_active=True, 
            created_by=profile.user
        )
        
        # Get the availability slot
        slot = AvailabilitySlot.objects.get(
            id=slot_id,
            salon=profile,
            is_booked=False
        )
        
        # Check slot is still available and not in past
        if slot.date < date.today():
            messages.error(request, 'This time slot is in the past.')
            return redirect('saloon:salon_profile', slug=slug)
        
        if slot.is_booked:
            messages.error(request, 'This time slot has just been booked. Please select another.')
            return redirect('saloon:salon_profile', slug=slug)
        
        # Create booking
        booking = Booking.objects.create(
            salon=profile,
            style=style,
            worker=slot.worker,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            booking_date=slot.date,
            booking_time=slot.start_time,
            duration_minutes=slot.duration_minutes,
            customer_notes=customer_notes,
            price=style.price,
            status='pending'
        )
        
        # Slot will be automatically marked as booked by the Booking.save() method
        
        # Send confirmation emails
        try:
            if customer_email:
                send_customer_booking_email(booking)
        except Exception as e:
            logger.error(f"Failed to send customer email: {str(e)}")
        
        try:
            send_owner_booking_email(booking)
        except Exception as e:
            logger.error(f"Failed to send owner email: {str(e)}")
        
        messages.success(
            request, 
            f'✓ Booking created successfully! Your booking number is {booking.booking_number}.'
        )
        return redirect('saloon:salon_profile', slug=slug)
        
    except Style.DoesNotExist:
        messages.error(request, 'Selected service is no longer available.')
        return redirect('saloon:salon_profile', slug=slug)
    
    except AvailabilitySlot.DoesNotExist:
        messages.error(request, 'Selected time slot is no longer available.')
        return redirect('saloon:salon_profile', slug=slug)
    
    except Exception as e:
        messages.error(request, 'Error creating booking. Please try again.')
        logger.error(f"Error creating booking: {str(e)}", exc_info=True)
        return redirect('saloon:salon_profile', slug=slug)
    
from datetime import datetime, date
from django.utils import timezone



def send_customer_booking_email(booking):
    """Send booking confirmation email to customer"""
    try:
        subject = f'Booking Confirmation - {booking.booking_number}'
        
        # Render HTML email
        html_message = render_to_string('saloon/customer_booking_confirmation.html', {
            'booking': booking,
            'salon': booking.salon,
            'customer_name': booking.customer_name,
        })
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.customer_email],
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        return True
        
    except Exception as e:
        logger.error(f"Error sending customer email: {str(e)}", exc_info=True)
        print(f"Error sending customer email: {e}")
        return False


def send_owner_booking_email(booking):
    """Send new booking notification to salon owner"""
    try:
        subject = f'New Booking - {booking.booking_number}'
        
        # Render HTML email
        html_message = render_to_string('saloon/owner_booking_notification.html', {
            'booking': booking,
            'salon': booking.salon,
        })
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        # Create email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.salon.user.email],
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        return True
        
    except Exception as e:
        logger.error(f"Error sending owner email: {str(e)}", exc_info=True)
        print(f"Error sending owner email: {e}")
        return False

@login_required
@login_required
def update_booking_status(request, booking_id):
    """Update booking status - OWNER ONLY (requires login)"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, salon__user=request.user)
        new_status = request.POST.get('status')
        cancellation_reason = request.POST.get('cancellation_reason', '')
        
        if new_status in ['confirmed', 'cancelled', 'completed']:
            old_status = booking.status
            booking.status = new_status
            
            if new_status == 'confirmed':
                booking.confirmed_at = datetime.now()
                # Send confirmation email
                send_booking_confirmation_email(booking)
                messages.success(request, f'Booking {booking.booking_number} confirmed. Customer has been notified via email.')
                
            elif new_status == 'completed':
                booking.completed_at = datetime.now()
                messages.success(request, f'Booking {booking.booking_number} marked as completed.')
                
            elif new_status == 'cancelled':
                booking.cancelled_at = datetime.now()
                booking.cancelled_by = 'salon'
                booking.cancellation_reason = cancellation_reason
                # Send cancellation email
                send_booking_cancellation_email(booking, cancelled_by='salon')
                messages.success(request, f'Booking {booking.booking_number} cancelled. Customer has been notified via email.')
            
            booking.save()
        
        return redirect('saloon:manage_availability')
    
    return redirect('saloon:manage_availability')


def send_booking_confirmation_email(booking):
    """Send confirmation email when salon confirms booking"""
    try:
        subject = f'Booking Confirmed - {booking.booking_number}'
        
        html_message = render_to_string('saloon/booking_confirmed.html', {
            'booking': booking,
            'salon': booking.salon,
        })
        
        plain_message = strip_tags(html_message)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.customer_email] if booking.customer_email else [],
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
        return True
        
    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}", exc_info=True)
        return False


def send_booking_cancellation_email(booking, cancelled_by='salon'):
    """Send cancellation email"""
    try:
        subject = f'Booking Cancelled - {booking.booking_number}'
        
        html_message = render_to_string('saloon/booking_cancelled.html', {
            'booking': booking,
            'salon': booking.salon,
            'cancelled_by': cancelled_by,
        })
        
        plain_message = strip_tags(html_message)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[booking.customer_email] if booking.customer_email else [],
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
        return True
        
    except Exception as e:
        logger.error(f"Error sending cancellation email: {str(e)}", exc_info=True)
        return False

@login_required
def get_customer_emails(request):
    """AJAX endpoint to get existing customer emails for autocomplete"""
    user = request.user
    
    # Get emails from StyleTicket
    style_ticket_emails = StyleTicket.objects.filter(
        created_by=user,
        customer_email__isnull=False
    ).exclude(customer_email='').values('customer_email', 'customer_name', 'customer_phone').distinct()
    
    # Get emails from Booking (if applicable)
    booking_emails = []
    try:
        booking_emails = Booking.objects.filter(
            salon__user=user,
            customer_email__isnull=False
        ).exclude(customer_email='').values('customer_email', 'customer_name', 'customer_phone').distinct()
    except:
        pass
    
    # Combine and deduplicate
    all_emails = {}
    for item in style_ticket_emails:
        if item['customer_email']:
            all_emails[item['customer_email']] = {
                'email': item['customer_email'],
                'name': item['customer_name'],
                'phone': item['customer_phone']
            }
    
    for item in booking_emails:
        if item['customer_email'] and item['customer_email'] not in all_emails:
            all_emails[item['customer_email']] = {
                'email': item['customer_email'],
                'name': item['customer_name'],
                'phone': item['customer_phone']
            }
    
    # Convert to list
    emails_list = list(all_emails.values())
    
    return JsonResponse({
        'emails': emails_list
    })

# Everything below is for the AI Assistant feature

import logging
logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def salon_ai_chat_endpoint(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        logger.info(f"AI Chat request from user {request.user.username}: {user_message}")
        
        # Get salon-specific data
        salon_data = get_salon_business_data(request.user)
        logger.info(f"Salon data retrieved successfully for user {request.user.username}")
        
        # Generate AI response using salon data
        ai_response = generate_salon_ai_response(user_message, salon_data)
        logger.info(f"AI response generated successfully")
        
        return JsonResponse({
            'success': True,
            'response': ai_response
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Error in salon_ai_chat_endpoint: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)



def get_salon_business_data(user):
    """Extract salon-specific business data for the given user including bookings"""
    try:
        # Get all salon data for this user
        styles = Style.objects.filter(created_by=user)
        style_tickets = StyleTicket.objects.filter(created_by=user)
        workers = Worker.objects.filter(created_by=user)
        bookings = Booking.objects.filter(salon__user=user)
        
        # Current date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today.replace(day=1)
        
        # Filter completed bookings
        completed_bookings = bookings.filter(status='completed')
        
        # Basic metrics - COMBINED (StyleTickets + Bookings)
        style_tickets_revenue = style_tickets.filter(completed=True).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        bookings_revenue = completed_bookings.aggregate(
            total=Sum('price')
        )['total'] or 0
        
        total_revenue = style_tickets_revenue + bookings_revenue
        
        # Counts - COMBINED
        total_completed_style_tickets = style_tickets.filter(completed=True).count()
        total_completed_bookings = completed_bookings.count()
        total_completed_appointments = total_completed_style_tickets + total_completed_bookings
        
        total_style_tickets_count = style_tickets.count()
        total_bookings_count = bookings.count()
        total_appointments_count = total_style_tickets_count + total_bookings_count
        
        # Time-based analysis - COMBINED
        today_style_tickets = style_tickets.filter(created_at__date=today)
        today_bookings = bookings.filter(booking_date=today, status='completed')
        
        today_style_revenue = today_style_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
        today_booking_revenue = today_bookings.aggregate(total=Sum('price'))['total'] or 0
        today_revenue = today_style_revenue + today_booking_revenue
        
        week_style_tickets = style_tickets.filter(created_at__date__gte=week_ago)
        week_bookings = bookings.filter(booking_date__gte=week_ago, status='completed')
        
        week_style_revenue = week_style_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
        week_booking_revenue = week_bookings.aggregate(total=Sum('price'))['total'] or 0
        week_revenue = week_style_revenue + week_booking_revenue
        
        month_style_tickets = style_tickets.filter(created_at__date__gte=month_ago)
        month_bookings = bookings.filter(booking_date__gte=month_ago, status='completed')
        
        month_style_revenue = month_style_tickets.aggregate(total=Sum('total_amount'))['total'] or 0
        month_booking_revenue = month_bookings.aggregate(total=Sum('price'))['total'] or 0
        month_revenue = month_style_revenue + month_booking_revenue
        
        # Style performance analysis (from both StyleTickets and Bookings)
        style_performance = styles.annotate(
            # StyleTickets stats
            style_tickets_count=Count('style_tickets'),
            style_tickets_revenue=Sum('style_tickets__total_amount'),
            # Bookings stats
            bookings_count=Count('bookings', filter=Q(bookings__status='completed')),
            bookings_revenue=Sum('bookings__price', filter=Q(bookings__status='completed'))
        ).annotate(
            # Combined totals with explicit output_field
            total_tickets_count=ExpressionWrapper(
                F('style_tickets_count') + F('bookings_count'),
                output_field=IntegerField()
            ),
            total_revenue=ExpressionWrapper(
                Coalesce(F('style_tickets_revenue'), 0, output_field=DecimalField()) + 
                Coalesce(F('bookings_revenue'), 0, output_field=DecimalField()),
                output_field=DecimalField()
            )
        ).order_by('-total_revenue')
        
        # Worker performance (from both StyleTickets and Bookings)
        worker_performance = workers.annotate(
            # StyleTickets stats
            style_tickets_completed=Count('style_tickets', filter=Q(style_tickets__completed=True)),
            style_tickets_revenue=Sum('style_tickets__total_amount', filter=Q(style_tickets__completed=True)),
            # Bookings stats
            bookings_completed=Count('bookings', filter=Q(bookings__status='completed')),
            bookings_revenue=Sum('bookings__price', filter=Q(bookings__status='completed'))
        ).annotate(
            # Combined totals with explicit output_field
            total_completed=ExpressionWrapper(
                F('style_tickets_completed') + F('bookings_completed'),
                output_field=IntegerField()
            ),
            total_revenue=ExpressionWrapper(
                Coalesce(F('style_tickets_revenue'), 0, output_field=DecimalField()) + 
                Coalesce(F('bookings_revenue'), 0, output_field=DecimalField()),
                output_field=DecimalField()
            )
        ).order_by('-total_revenue')
        
        # Popular styles (top 3)
        popular_styles = list(style_performance.filter(total_tickets_count__gt=0)[:3])
        
        # Calculate average appointment value
        avg_appointment_value = 0
        if total_completed_appointments > 0:
            avg_appointment_value = total_revenue / total_completed_appointments
        
        # Calculate completion rate
        completion_rate = 0
        if total_appointments_count > 0:
            completion_rate = (total_completed_appointments / total_appointments_count) * 100
        
        # Breakdown by type for detailed analysis
        revenue_breakdown = {
            'style_tickets': float(style_tickets_revenue),
            'bookings': float(bookings_revenue),
            'total': float(total_revenue)
        }
        
        appointments_breakdown = {
            'style_tickets': total_completed_style_tickets,
            'bookings': total_completed_bookings,
            'total': total_completed_appointments
        }
        
        return {
            # Basic business metrics - COMBINED
            'total_styles': styles.count(),
            'total_workers': workers.count(),
            'total_revenue': float(total_revenue),
            'total_completed_appointments': total_completed_appointments,
            'total_appointments_count': total_appointments_count,
            
            # Revenue breakdown
            'revenue_breakdown': revenue_breakdown,
            'appointments_breakdown': appointments_breakdown,
            
            # Time-based performance - COMBINED
            'today': {
                'tickets': today_style_tickets.count() + today_bookings.count(),
                'revenue': float(today_revenue),
                'breakdown': {
                    'style_tickets': today_style_tickets.count(),
                    'bookings': today_bookings.count(),
                    'style_revenue': float(today_style_revenue),
                    'booking_revenue': float(today_booking_revenue)
                }
            },
            'this_week': {
                'tickets': week_style_tickets.count() + week_bookings.count(),
                'revenue': float(week_revenue),
                'breakdown': {
                    'style_tickets': week_style_tickets.count(),
                    'bookings': week_bookings.count(),
                    'style_revenue': float(week_style_revenue),
                    'booking_revenue': float(week_booking_revenue)
                }
            },
            'this_month': {
                'tickets': month_style_tickets.count() + month_bookings.count(),
                'revenue': float(month_revenue),
                'breakdown': {
                    'style_tickets': month_style_tickets.count(),
                    'bookings': month_bookings.count(),
                    'style_revenue': float(month_style_revenue),
                    'booking_revenue': float(month_booking_revenue)
                }
            },
            
            # Style analysis - COMBINED
            'style_performance': [
                {
                    'name': style.name,
                    'price': float(style.price),
                    'total_tickets_count': style.total_tickets_count or 0,
                    'total_revenue': float(style.total_revenue or 0),
                    'breakdown': {
                        'style_tickets_count': style.style_tickets_count or 0,
                        'bookings_count': style.bookings_count or 0,
                        'style_tickets_revenue': float(style.style_tickets_revenue or 0),
                        'bookings_revenue': float(style.bookings_revenue or 0)
                    }
                }
                for style in popular_styles
            ],
            
            # Worker performance - COMBINED
            'worker_performance': [
                {
                    'name': f"{worker.name} {worker.surname}",
                    'total_completed': worker.total_completed or 0,
                    'total_revenue_generated': float(worker.total_revenue or 0),
                    'breakdown': {
                        'style_tickets_completed': worker.style_tickets_completed or 0,
                        'bookings_completed': worker.bookings_completed or 0,
                        'style_tickets_revenue': float(worker.style_tickets_revenue or 0),
                        'bookings_revenue': float(worker.bookings_revenue or 0)
                    }
                }
                for worker in worker_performance if worker.total_completed > 0
            ],
            
            # Business health metrics
            'avg_appointment_value': float(avg_appointment_value),
            'completion_rate': float(completion_rate),
            
            'user_business_name': f"{user.username}'s Salon"
        }
        
    except Exception as e:
        logger.error(f"Error in get_salon_business_data: {str(e)}")
        # Return minimal data to avoid complete failure
        return {
            'total_styles': 0,
            'total_workers': 0,
            'total_revenue': 0,
            'total_completed_appointments': 0,
            'total_appointments_count': 0,
            'revenue_breakdown': {'style_tickets': 0, 'bookings': 0, 'total': 0},
            'appointments_breakdown': {'style_tickets': 0, 'bookings': 0, 'total': 0},
            'today': {'tickets': 0, 'revenue': 0, 'breakdown': {'style_tickets': 0, 'bookings': 0, 'style_revenue': 0, 'booking_revenue': 0}},
            'this_week': {'tickets': 0, 'revenue': 0, 'breakdown': {'style_tickets': 0, 'bookings': 0, 'style_revenue': 0, 'booking_revenue': 0}},
            'this_month': {'tickets': 0, 'revenue': 0, 'breakdown': {'style_tickets': 0, 'bookings': 0, 'style_revenue': 0, 'booking_revenue': 0}},
            'style_performance': [],
            'worker_performance': [],
            'avg_appointment_value': 0,
            'completion_rate': 0,
            'user_business_name': 'Your Salon'
        }

def generate_salon_ai_response(user_message, salon_data):
    """Use OpenAI API to generate salon-specific intelligent responses"""
    
    # Prepare salon-specific context
    context = f"""
    SALON BUSINESS DATA:

    BUSINESS OVERVIEW:
    - Total Styles Offered: {salon_data['total_styles']}
    - Active Workers: {salon_data['total_workers']}
    - Total Revenue: R{salon_data['total_revenue']:,.2f}
    - Completed Appointments: {salon_data['total_completed_appointments']}
    - Total Appointments: {salon_data['total_appointments_count']}
    - Completion Rate: {salon_data['completion_rate']:.1f}%
    - Average Appointment Value: R{salon_data['avg_appointment_value']:,.2f}

    TODAY'S PERFORMANCE:
    - Appointments: {salon_data['today']['tickets']}
    - Revenue: R{salon_data['today']['revenue']:,.2f}
    - Breakdown: {salon_data['today']['breakdown']['style_tickets']} style tickets, {salon_data['today']['breakdown']['bookings']} bookings

    THIS WEEK:
    - Appointments: {salon_data['this_week']['tickets']}
    - Revenue: R{salon_data['this_week']['revenue']:,.2f}
    - Breakdown: {salon_data['this_week']['breakdown']['style_tickets']} style tickets, {salon_data['this_week']['breakdown']['bookings']} bookings

    THIS MONTH:
    - Appointments: {salon_data['this_month']['tickets']}
    - Revenue: R{salon_data['this_month']['revenue']:,.2f}
    - Breakdown: {salon_data['this_month']['breakdown']['style_tickets']} style tickets, {salon_data['this_month']['breakdown']['bookings']} bookings

    REVENUE BREAKDOWN:
    - Style Tickets: R{salon_data['revenue_breakdown']['style_tickets']:,.2f}
    - Bookings: R{salon_data['revenue_breakdown']['bookings']:,.2f}
    - Total: R{salon_data['revenue_breakdown']['total']:,.2f}

    APPOINTMENTS BREAKDOWN:
    - Style Tickets: {salon_data['appointments_breakdown']['style_tickets']}
    - Bookings: {salon_data['appointments_breakdown']['bookings']}
    - Total: {salon_data['appointments_breakdown']['total']}

    USER QUESTION: {user_message}
    """
    
    # Salon-specific system prompt
    system_prompt = """You are an intelligent salon management assistant specializing in hair styling and beauty services.
    Provide helpful, professional responses about salon operations, appointments, and business performance.
    Be concise and focus on the data provided. Note that this salon uses two systems: Style Tickets and Bookings."""
    
    try:
        # Check if OpenAI API key is available
        if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not found, using fallback response")
            return generate_salon_fallback_response(user_message, salon_data)
        
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
        return generate_salon_fallback_response(user_message, salon_data)
    
def generate_salon_fallback_response(user_message, salon_data):
    """Fallback response when OpenAI is unavailable"""
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ['revenue', 'income', 'money']):
        return f"💰 Your salon has generated R{salon_data['total_revenue']:,.2f} in total revenue. This month: R{salon_data['this_month']['revenue']:,.2f}. Breakdown: Style Tickets: R{salon_data['revenue_breakdown']['style_tickets']:,.2f}, Bookings: R{salon_data['revenue_breakdown']['bookings']:,.2f}"
    
    elif any(word in message_lower for word in ['appointment', 'booking', 'ticket']):
        return f"📅 You have {salon_data['total_completed_appointments']} completed appointments out of {salon_data['total_appointments_count']} total. Completion rate: {salon_data['completion_rate']:.1f}%. Breakdown: {salon_data['appointments_breakdown']['style_tickets']} style tickets, {salon_data['appointments_breakdown']['bookings']} bookings"
    
    elif any(word in message_lower for word in ['today']):
        return f"📊 Today: {salon_data['today']['tickets']} appointments (Style Tickets: {salon_data['today']['breakdown']['style_tickets']}, Bookings: {salon_data['today']['breakdown']['bookings']}), R{salon_data['today']['revenue']:,.2f} revenue"
    
    elif any(word in message_lower for word in ['worker', 'stylist']):
        if salon_data['worker_performance']:
            top_worker = salon_data['worker_performance'][0]
            return f"👩‍💼 Your top stylist is {top_worker['name']} with {top_worker['total_completed']} appointments and R{top_worker['total_revenue_generated']:,.2f} revenue"
        else:
            return f"👩‍💼 You have {salon_data['total_workers']} stylists working at your salon."
    
    elif any(word in message_lower for word in ['style', 'service']):
        if salon_data['style_performance']:
            top_style = salon_data['style_performance'][0]
            return f"💇 Most popular style: {top_style['name']} with {top_style['total_tickets_count']} appointments (R{top_style['total_revenue']:,.2f})"
        else:
            return f"💇 You offer {salon_data['total_styles']} different styles at your salon."
    
    elif any(word in message_lower for word in ['week', 'weekly']):
        return f"📈 This week: {salon_data['this_week']['tickets']} appointments, R{salon_data['this_week']['revenue']:,.2f} revenue"
    
    elif any(word in message_lower for word in ['month', 'monthly']):
        return f"📅 This month: {salon_data['this_month']['tickets']} appointments, R{salon_data['this_month']['revenue']:,.2f} revenue"
    
    else:
        return f"💈 Salon Overview: {salon_data['total_styles']} styles, {salon_data['total_workers']} workers, R{salon_data['total_revenue']:,.2f} total revenue. {salon_data['total_completed_appointments']} completed appointments. Ask me about appointments, revenue, stylist performance, or style popularity!"