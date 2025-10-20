from django.contrib import admin

from .models import Worker, Style, StyleTicket

admin.site.register(Worker)
admin.site.register(Style)
admin.site.register(StyleTicket)

