import os
from pathlib import Path
from google.oauth2 import service_account
from decouple import config, Csv
import dj_database_url


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='.vercel.app,127.0.0.1,localhost,.com,096351469dad.ngrok-free.app').split(',')
ADMIN_PATH = config('ADMIN_PATH')

CSRF_TRUSTED_ORIGINS = [
    "https://096351469dad.ngrok-free.app",
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'whitenoise.runserver_nostatic',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'core',
    'submit',
    'rest_framework',
    'crispy_forms',
    'django.contrib.humanize',
    "django.contrib.sites",
    "allauth",
    "axes",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "django_recaptcha",
    "carwash",
    "saloon",
    "email_campaigns",
    'django_filters',
    'corsheaders',
    'storages',
    'social_django', 
    'csp',
    'django_rq',
    
    


]
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email"
        ],
       "AUTH_PARAMS": {"access_type": "online"}
    }
}


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'axes.middleware.AxesMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
]
AUTH_USER_MODEL = 'submit.CustomUser'
ROOT_URLCONF = 'core.project.urls'
SITE_ID=2
SOCIALACCOUNT_LOGIN_ON_GET = True  
AUTHENTICATION_BACKENDS = [
    'submit.backends.EmailOrPhoneBackend',  
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'axes.backends.AxesStandaloneBackend',
    'social_core.backends.google.GoogleOAuth2',
]

ASGI_APPLICATION = 'core.project.asgi.application'


OPENAI_API_KEY = config('OPENAI_API_KEY')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

CRISPY_TEMPLATE_PACK = 'bootstrap4'  


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'submit.context_processors.subscription_status',
            ],
        },
    },
]


#DATABASES = {
#    'default': {
#        'ENGINE': config('DATABASE_ENGINE'),
#        'NAME': config('DATABASE_NAME'),
#        'USER': config('DATABASE_USER'),
#        'PASSWORD': config('DATABASE_PASSWORD'),
#        'HOST': config('DATABASE_HOST'),
#        'PORT': config('DATABASE_PORT'),
#    }
#}

DATABASE_URL = config('DATABASE_URL')

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600
    )
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config('CELERY_BROKER_URL'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}


redis_url = config('REDIS_URL')
if redis_url:
    RQ_QUEUES = {
        'default': {
            'URL': redis_url,
            'DEFAULT_TIMEOUT': 360,
        },
    }
# Celery settings

CELERY_BROKER_URL = config('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes




AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # For development - change for production
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'TIME_FORMAT': '%H:%M:%S',
}


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Johannesburg'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, "project/static")]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


DEFAULT_FILE_STORAGE = 'email_campaigns.storage.GoogleCloudMediaFileStorage'  # Update path

GS_PROJECT_ID = config('GS_PROJECT_ID')
GS_BUCKET_NAME = config('GS_BUCKET_NAME')
MEDIA_ROOT = 'media/' 
MEDIA_URL = f'https://storage.googleapis.com/{GS_BUCKET_NAME}/'  # Fixed MEDIA_URL

GS_CREDENTIALS = service_account.Credentials.from_service_account_info({
    "type": config("GOOGLE_CLOUD_TYPE", default="service_account"),
    "project_id": config("GOOGLE_CLOUD_PROJECT_ID"),
    "private_key_id": config("GOOGLE_CLOUD_PRIVATE_KEY_ID"),
    "private_key": config("GOOGLE_CLOUD_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": config("GOOGLE_CLOUD_CLIENT_EMAIL"),
    "client_id": config("GOOGLE_CLOUD_CLIENT_ID"),
    "auth_uri": config("GOOGLE_CLOUD_AUTH_URI", default="https://accounts.google.com/o/oauth2/auth"),
    "token_uri": config("GOOGLE_CLOUD_TOKEN_URI", default="https://oauth2.googleapis.com/token"),
    "auth_provider_x509_cert_url": config("GOOGLE_CLOUD_AUTH_PROVIDER_X509_CERT_URL", default="https://www.googleapis.com/oauth2/v1/certs"),
    "client_x509_cert_url": config("GOOGLE_CLOUD_CLIENT_X509_CERT_URL"),
    "universe_domain": config("GOOGLE_CLOUD_UNIVERSE_DOMAIN", default="googleapis.com")
})
GS_DEFAULT_ACL = 'publicRead'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = config('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = config('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET')



SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]

# Custom pipeline to handle incomplete profiles
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'submit.pipeline.save_profile_data',  # Custom pipeline step
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'submit.pipeline.redirect_to_complete_profile',  # Custom redirect
)

# URLs for redirects
LOGIN_REDIRECT_URL = '/complete-profile/'  # Will be handled by custom pipeline
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/complete-profile/'



EMAIL_BACKEND = config('EMAIL_BACKEND')
EMAIL_PORT = config('EMAIL_PORT')
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('ADMIN_EMAIL')
EMAIL_USE_SSL = config('EMAIL_USE_SSL', cast=bool)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
ADMIN_EMAIL = config('ADMIN_EMAIL')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')

GMAIL_HOST = config('GMAIL_HOST')
GMAIL_PORT = config('GMAIL_PORT')
GMAIL_USE_TLS = config('GMAIL_USE_TLS')
GMAIL_USE_SSL = config('GMAIL_USE_SSL')
GMAIL_HOST_USER = config('GMAIL_HOST_USER')  # kasi@gmail.com
GMAIL_HOST_PASSWORD = config('GMAIL_HOST_PASSWORD')  # App password
GMAIL_FROM_EMAIL = config('GMAIL_FROM_EMAIL')  # kasi@gmail.com

#LOGIN_REDIRECT_URL = '/'
#LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = 'login'


PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY')
SITE_URL = 'http://127.0.0.1:8000'
SITE_URL = 'https://kasiledger.com' 



RECAPTCHA_PUBLIC_KEY = config('RECAPTCHA_PUBLIC_KEY')
RECAPTCHA_PRIVATE_KEY = config('RECAPTCHA_PRIVATE_KEY')

SILENCED_SYSTEM_CHECKS = config('SILENCED_SYSTEM_CHECKS', cast=Csv())

AXES_FAILURE_LIMIT = config('AXES_FAILURE_LIMIT', cast=int)

AXES_COOLOFF_TIME = 1

AXES_ONLY_ADMIN_SITE = config('AXES_ONLY_ADMIN_SITE', cast=bool)

AXES_LOCKOUT_TEMPLATE = config('AXES_LOCKOUT_TEMPLATE')

AXES_LOCKOUT_URL = config('AXES_LOCKOUT_URL')
AXES_USERNAME_FORM_FIELD = config('AXES_USERNAME_FORM_FIELD')

AXES_RESET_ON_SUCCESS = config('AXES_RESET_ON_SUCCESS', cast=bool)

AXES_NEVER_LOCKOUT_WHITELIST = config('AXES_NEVER_LOCKOUT_WHITELIST',
                                      cast=bool)
AXES_IP_WHITELIST = config('AXES_IP_WHITELIST', cast=Csv())

AXES_ENABLE_ACCESS_FAILURE_LOG = config('AXES_ENABLE_ACCESS_FAILURE_LOG',
                                        cast=bool)

AXES_RESET_ON_SUCCESS = config('AXES_RESET_ON_SUCCESS', cast=bool)

AXES_LOCKOUT_PARAMETERS = config('AXES_LOCKOUT_PARAMETERS', cast=Csv())


# Trust Railway's reverse proxy headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SAMESITE = 'Strict'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

if not DEBUG:
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 15768000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
    SESSION_COOKIE_NAME = '__Host-sessionid'
    CSRF_COOKIE_NAME = '__Host-csrftoken'
else:
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0



CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),

        "script-src": (
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            "https://static.cloudflareinsights.com",
            "https://cdnjs.cloudflare.com",  # ✅ allow Font Awesome JS (if used)
        ),

        "style-src": (
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
            "https://cdnjs.cloudflare.com",  # ✅ allow Font Awesome CSS
            "https://cdn.jsdelivr.net",      # optional — for JSDelivr-based assets
        ),

        "img-src": (
            "'self'",
            "data:",
            "https://*",
        ),

        "font-src": (
            "'self'",
            "https://fonts.gstatic.com",
            "https://cdnjs.cloudflare.com",  # ✅ allow font files from Cloudflare CDN
        ),

        "connect-src": (
            "'self'",
            "https://kasialgorithms.co.za",
            "https://api.kasialgorithms.co.za",
        ),

        "form-action": ("'self'",),
        "frame-ancestors": ("'none'",),
        "object-src": ("'none'",),
        "media-src": ("'self'",),
        "base-uri": ("'self'",),
    }
}

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = "same-origin"


