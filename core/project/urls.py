from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from core import views
from core.project.settings import ADMIN_PATH
from core.views import index, subscribe,  enquire, guide, delete_product, generate_barcodes, list_income_statements, subscribed, contact, terms, unsubscribed, optout, PostCreateView



urlpatterns = [
    path('', index, name='index'),
    #path("", include("googleauthentication.urls")),
    path('accounts/', include("allauth.urls")),
    path('admin/', admin.site.urls),
    path('subscribe/', subscribe, name='subscribe'),
    path('POS/', subscribed, name='subscribed'),
    path('generate/', views.generate_barcodes, name='generate_barcodes'),
    path('api/check-product/', views.check_product, name='check_product'),
    path('api/process-sale/', views.process_sale, name='process_sale'),
    path('product/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('', include('submit.urls')),
    path('enquire/', enquire, name='enquire'),
    path('guide/', guide, name='guide'),
    path('income-statement/create/',views.create_income_statement,name='create_income_statement'),
    path('income-statement/<int:pk>/',views.view_income_statement,name='view_income_statement'),
    path('Income statements/', list_income_statements, name='list_income_statements'),
    path('optout/', optout, name='optout'),
    path('post/new/', PostCreateView.as_view(), name='post-create'),
    path('inventory/', contact, name='contact'),
    path('terms/', terms, name='terms'),
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
