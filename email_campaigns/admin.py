from django.contrib import admin
from .models import *

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'is_system_template', 'created_at']
    list_filter = ['category', 'is_active', 'is_system_template']
    search_fields = ['name', 'subject']

@admin.register(CustomerEmail)
class CustomerEmailAdmin(admin.ModelAdmin):
    list_display = ['email', 'customer_name', 'user', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['email', 'customer_name', 'user__username']

@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'status', 'sent_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'user__username']

admin.site.register(CampaignRecipient)
admin.site.register(CampaignImage)