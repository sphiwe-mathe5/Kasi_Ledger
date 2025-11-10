from django.contrib import admin

from .models import Worker, Style, StyleTicket, AvailabilitySlot, RecurringAvailability

admin.site.register(Worker)
admin.site.register(Style)
admin.site.register(StyleTicket)
admin.site.register(AvailabilitySlot)
admin.site.register(RecurringAvailability)

