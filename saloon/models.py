# salon/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, time
from core.models import CustomUser

class Worker(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="worker_user")
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="workers_created")

    def __str__(self):
        return f"{self.name} {self.surname}"

    @property
    def full_name(self):
        return f"{self.name} {self.surname}"
    
    @property
    def styles_completed_count(self):
        return self.style_tickets.count()

    class Meta:
        ordering = ['name', 'surname']

class Style(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="styles_created")

    def __str__(self):
        return f"{self.name} - R{self.price}"

    class Meta:
        ordering = ['name']

class StyleTicket(models.Model):
    ticket_number = models.CharField(max_length=20, unique=True, blank=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=15, blank=True, null=True)
    customer_email = models.EmailField(blank=True, null=True)
    style = models.ForeignKey(Style, on_delete=models.CASCADE, related_name='style_tickets')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='style_tickets')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="style_tickets_created")
    completed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="style_tickets_completed")

    def save(self, *args, **kwargs):
        # Generate ticket number if not exists
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        
        # Set total amount from service price
        if self.style and not self.total_amount:
            self.total_amount = self.style.price
            
        super().save(*args, **kwargs)

    def generate_ticket_number(self):
        from datetime import datetime
        today = datetime.now().strftime('%Y%m%d')
        last_ticket = StyleTicket.objects.filter(
            ticket_number__startswith=f'SL{today}'
        ).order_by('-ticket_number').first()
        
        if last_ticket:
            last_number = int(last_ticket.ticket_number[-3:])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'SL{today}{new_number:03d}'

    def __str__(self):
        return f"{self.ticket_number} - {self.customer_name}"

    class Meta:
        ordering = ['-created_at']




#Everything about booking appointments

# salon/models.py - Add these models

class SalonProfile(models.Model):
    """Extended profile for salon owners"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='salon_profile')
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    bio = models.TextField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    #profile_image = models.ImageField(upload_to='salon_profiles/', blank=True, null=True)
    #cover_image = models.ImageField(upload_to='salon_covers/', blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = self.user.company_name or f"salon-{self.user.id}"
            self.slug = self.generate_unique_slug(base_slug)
        super().save(*args, **kwargs)

    def generate_unique_slug(self, base_slug):
        from django.utils.text import slugify
        slug = slugify(base_slug)
        unique_slug = slug
        counter = 1
        while SalonProfile.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{slug}-{counter}"
            counter += 1
        return unique_slug

    def __str__(self):
        return f"{self.user.company_name or self.user.email} - Profile"

    @property
    def booking_url(self):
        return f"/salon/{self.slug}"

    class Meta:
        ordering = ['-created_at']


class WorkingHours(models.Model):
    """Define salon working hours"""
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    salon = models.ForeignKey(SalonProfile, on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    is_closed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['salon', 'day_of_week']
        ordering = ['day_of_week']

    def __str__(self):
        return f"{self.salon.user.company_name} - {self.get_day_of_week_display()}"


class TimeOff(models.Model):
    """Handle salon holidays/days off"""
    salon = models.ForeignKey(SalonProfile, on_delete=models.CASCADE, related_name='time_off')
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['salon', 'date']

    def __str__(self):
        return f"{self.salon.user.company_name} - {self.date}"


class AvailabilitySlot(models.Model):
    """
    Represents available time slots that salon owners create.
    When a booking is made, the slot is marked as booked.
    """
    salon = models.ForeignKey(SalonProfile, on_delete=models.CASCADE, related_name='availability_slots')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, null=True, blank=True, related_name='availability_slots')
    
    # Date and time
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.IntegerField(default=60)  # How long each slot is
    
    # Status
    is_booked = models.BooleanField(default=False)
    booking = models.OneToOneField('Booking', on_delete=models.SET_NULL, null=True, blank=True, related_name='availability_slot')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['date', 'start_time']
        unique_together = ['salon', 'worker', 'date', 'start_time']
    
    def clean(self):
        # Validate that end_time is after start_time
        if self.end_time <= self.start_time:
            raise ValidationError('End time must be after start time')
        
        # Validate date is not in the past
        if self.date < timezone.now().date():
            raise ValidationError('Cannot create slots for past dates')
    
    def __str__(self):
        worker_name = self.worker.full_name if self.worker else "Any Worker"
        status = "Booked" if self.is_booked else "Available"
        salon_name = self.salon.user.company_name if hasattr(self.salon, 'user') else "Salon"
        return f"{salon_name} - {worker_name} - {self.date} {self.start_time} [{status}]"
    
    @property
    def is_available(self):
        """Check if slot is available for booking"""
        return not self.is_booked and self.date >= timezone.now().date()


class RecurringAvailability(models.Model):
    """
    Template for creating recurring availability slots (e.g., every Monday 9am-5pm)
    """
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    salon = models.ForeignKey('SalonProfile', on_delete=models.CASCADE, related_name='recurring_availability')
    worker = models.ForeignKey('Worker', on_delete=models.CASCADE, null=True, blank=True, related_name='recurring_availability')
    
    # Recurrence settings
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.IntegerField(default=60)
    
    # Date range for recurrence
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for indefinite")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['weekday', 'start_time']
    
    def __str__(self):
        worker_name = self.worker.full_name if self.worker else "Any Worker"
        salon_name = self.salon.user.company_name if hasattr(self.salon, 'user') else "Salon"
        return f"{salon_name} - {worker_name} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"
    
    def generate_slots_for_date_range(self, start_date, end_date):
        """Generate individual availability slots based on this recurring template"""
        from datetime import timedelta
        
        current_date = start_date
        slots_created = 0
        
        while current_date <= end_date:
            # Check if current date matches our weekday
            if current_date.weekday() == self.weekday:
                # Generate time slots for this day
                current_time = datetime.combine(current_date, self.start_time)
                end_datetime = datetime.combine(current_date, self.end_time)
                
                while current_time < end_datetime:
                    slot_end_time = (current_time + timedelta(minutes=self.slot_duration_minutes)).time()
                    
                    # Don't create slot if it goes past end_time
                    if slot_end_time > self.end_time:
                        break
                    
                    # Create slot if it doesn't exist
                    slot, created = AvailabilitySlot.objects.get_or_create(
                        salon=self.salon,
                        worker=self.worker,
                        date=current_date,
                        start_time=current_time.time(),
                        defaults={
                            'end_time': slot_end_time,
                            'duration_minutes': self.slot_duration_minutes,
                            'created_by': self.created_by
                        }
                    )
                    
                    if created:
                        slots_created += 1
                    
                    current_time += timedelta(minutes=self.slot_duration_minutes)
            
            current_date += timedelta(days=1)
        
        return slots_created


# Update the existing Booking model
class Booking(models.Model):
    """Updated booking model with availability slot link"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    booking_number = models.CharField(max_length=20, unique=True, blank=True)
    salon = models.ForeignKey('SalonProfile', on_delete=models.CASCADE, related_name='bookings')
    style = models.ForeignKey('Style', on_delete=models.CASCADE, related_name='bookings')
    worker = models.ForeignKey('Worker', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    
    # Customer info
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True, null=True)
    
    # Booking details
    booking_date = models.DateField()
    booking_time = models.TimeField()
    duration_minutes = models.IntegerField(default=60)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_required = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    deposit_paid = models.BooleanField(default=False)
    
    # Notes
    customer_notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings_created')

    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.booking_number = self.generate_booking_number()
        if not self.price:
            self.price = self.style.price
        
        # Mark availability slot as booked when booking is created
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.status in ['pending', 'confirmed']:
            self.mark_slot_as_booked()

    def generate_booking_number(self):
        from datetime import datetime
        today = datetime.now().strftime('%Y%m%d')
        last_booking = Booking.objects.filter(
            booking_number__startswith=f'BK{today}'
        ).order_by('-booking_number').first()
        
        if last_booking:
            last_number = int(last_booking.booking_number[-4:])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'BK{today}{new_number:04d}'
    
    def mark_slot_as_booked(self):
        """Mark the corresponding availability slot as booked"""
        try:
            slot = AvailabilitySlot.objects.get(
                salon=self.salon,
                worker=self.worker,
                date=self.booking_date,
                start_time=self.booking_time,
                is_booked=False
            )
            slot.is_booked = True
            slot.booking = self
            slot.save()
        except AvailabilitySlot.DoesNotExist:
            # Slot doesn't exist, which is fine for backwards compatibility
            pass
    
    def release_slot(self):
        """Release the availability slot when booking is cancelled"""
        try:
            slot = AvailabilitySlot.objects.get(booking=self)
            slot.is_booked = False
            slot.booking = None
            slot.save()
        except AvailabilitySlot.DoesNotExist:
            pass
    
    def delete(self, *args, **kwargs):
        """Release slot when booking is deleted"""
        self.release_slot()
        super().delete(*args, **kwargs)

    @property
    def end_time(self):
        from datetime import datetime, timedelta
        start = datetime.combine(self.booking_date, self.booking_time)
        end = start + timedelta(minutes=self.duration_minutes)
        return end.time()

    def is_conflicting(self):
        """Check if this booking conflicts with others - now uses availability slots"""
        # Check if there's an available slot for this time
        try:
            slot = AvailabilitySlot.objects.get(
                salon=self.salon,
                worker=self.worker,
                date=self.booking_date,
                start_time=self.booking_time
            )
            # Conflict if slot is already booked by someone else
            return slot.is_booked and slot.booking != self
        except AvailabilitySlot.DoesNotExist:
            # If no slot exists, check traditional way
            from datetime import datetime, timedelta
            
            start = datetime.combine(self.booking_date, self.booking_time)
            end = start + timedelta(minutes=self.duration_minutes)
            
            conflicting = Booking.objects.filter(
                salon=self.salon,
                worker=self.worker,
                booking_date=self.booking_date,
                status__in=['pending', 'confirmed']
            ).exclude(id=self.id)
            
            for booking in conflicting:
                other_start = datetime.combine(booking.booking_date, booking.booking_time)
                other_end = other_start + timedelta(minutes=booking.duration_minutes)
                
                if (start < other_end and end > other_start):
                    return True
            
            return False

    def __str__(self):
        return f"{self.booking_number} - {self.customer_name} on {self.booking_date}"

    class Meta:
        ordering = ['-booking_date', '-booking_time']


class Review(models.Model):
    """Customer reviews for salons"""
    salon = models.ForeignKey(SalonProfile, on_delete=models.CASCADE, related_name='reviews')
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review', null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)  # If from actual booking

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update salon average rating
        self.update_salon_rating()

    def update_salon_rating(self):
        from django.db.models import Avg, Count
        stats = Review.objects.filter(salon=self.salon).aggregate(
            avg_rating=Avg('rating'),
            total=Count('id')
        )
        self.salon.rating = stats['avg_rating'] or 0
        self.salon.total_reviews = stats['total']
        self.salon.save()

    def __str__(self):
        return f"{self.customer_name} - {self.rating}★ for {self.salon.user.company_name}"

    class Meta:
        ordering = ['-created_at']