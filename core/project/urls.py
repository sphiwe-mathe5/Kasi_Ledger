from django.contrib import admin
from django.urls import path, include
from django_otp.admin import OTPAdminSite
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin
from core.models import Product, IncomeStatement, Category, EmailTemplate, SentEmail, POSProduct
from submit.models import Profile, CustomUser, SubscriptionPlan, Subscription
from carwash.models import Employee, Service, ServiceTicket
from saloon.models import Worker, Style, StyleTicket
from email_campaigns.models import EmailTemplate, CustomerEmail, EmailCampaign, CampaignRecipient, CampaignImage
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.contrib.auth.models import User
from django.conf.urls.static import static
from core import views
from axes.models import AccessAttempt, AccessLog
from core.project.settings import ADMIN_PATH
from core.views import index, subscribe,  enquire, email, guide, delete_product, generate_barcodes, list_income_statements, contact, unsubscribed, optout, PostCreateView

class OTPAdmin(OTPAdminSite):
    pass

admin_site = OTPAdmin(name='OTPAdmin')
admin_site.register(User)
admin_site.register(TOTPDevice, TOTPDeviceAdmin)
admin_site.register(Profile)
admin_site.register(Category)
admin_site.register(IncomeStatement)
admin_site.register(Product)
admin_site.register(AccessAttempt)
admin_site.register(AccessLog)
#admin_site.register(EmailTemplate)
admin_site.register(SentEmail)
admin_site.register(POSProduct)
admin_site.register(SubscriptionPlan)
admin_site.register(Subscription)
admin_site.register(Worker)
admin_site.register(Style)
admin_site.register(StyleTicket)
admin_site.register(Employee)
admin_site.register(Service)
admin_site.register(ServiceTicket)

admin_site.register(EmailTemplate)
admin_site.register(CustomerEmail)
admin_site.register(EmailCampaign)
admin_site.register(CampaignRecipient)
admin_site.register(CampaignImage)

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'is_staff', 'is_active', 'is_authorized')
    list_filter = ('is_staff', 'is_active', 'is_authorized')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username', 'first_name', 'last_name', 'company_category', 'company_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_authorized',
                                  'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)

admin_site.register(CustomUser, CustomUserAdmin)

from rest_framework.routers import DefaultRouter
from core.views import AIRecognizeAPIView, AICommitAPIView, ai_stock_page
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import ProductViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)


urlpatterns = [
    path('', index, name='index'),

    
    path('', include(router.urls)),
    path('django-rq/', include('django_rq.urls')),

    path('ai-stock/', ai_stock_page, name='ai_stock_page'),
    path('api/ai-stock/recognize/', AIRecognizeAPIView.as_view(), name='ai_recognize'),
    path('api/ai-stock/commit/', AICommitAPIView.as_view(), name='ai_commit'),

    path('inventory/lock/', views.lock_transactions, name='lock_transactions'),

    path('auth/', include('social_django.urls', namespace='social')),

    path('ai-chat/', views.ai_chat_endpoint, name='ai_chat'),

    path('console/', views.console, name='console'),
    #path("", include("googleauthentication.urls")),
    path('accounts/', include("allauth.urls")),
    #path('admin/', admin.site.urls),
    path('kasiledger-safe-admin/', admin_site.urls),
    path('subscribe/', subscribe, name='subscribe'),
    path('POS/', views.pos, name='pos'),
    path('generate/', views.generate_barcodes, name='generate_barcodes'),
    path('api/check-product/', views.check_product, name='check_product'),
    path('api/process-sale/', views.process_sale, name='process_sale'),
    path('product/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('', include('submit.urls')),
    path('', include('carwash.urls')),
    path('', include('saloon.urls')),
    path('', include('email_campaigns.urls')),
    path('enquire/', enquire, name='enquire'),
    path('send/', views.send_email, name='send_email'),

    path('food-pos', views.pos_view, name='pos_view'),
    path('add-product/', views.add_product, name='add_product'),
    path('complete-sale/', views.complete_sale, name='complete_sale'),
    path('mark-collected/<int:order_id>/', views.mark_collected, name='mark_collected'),
    path('analytics/', views.sales_analytics, name='sales_analytics'),

    path('guide/', guide, name='guide'),
    path('email/', email, name='email'),
    path('income-statement/create/',views.create_income_statement,name='create_income_statement'),
    path('income-statement/<int:pk>/',views.view_income_statement,name='view_income_statement'),
    path('Income-statements/', list_income_statements, name='list_income_statements'),
    path('optout/', optout, name='optout'),
    path('post/new/', PostCreateView.as_view(), name='post-create'),
    path('inventory/', contact, name='contact'),
    path('unsubscribed/', unsubscribed, name='unsubscribed'),
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='submit/password_reset.html'),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='submit/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='submit/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='submit/password_reset_complete.html'),
         name='password_reset_complete'),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
