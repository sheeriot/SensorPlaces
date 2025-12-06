"""
Django settings for sensorplaces project.
"""


from pathlib import Path
import os
import time

from icecream import ic


# Application version for cache-busting
APP_VERSION = os.environ.get('APP_VERSION', str(int(time.time())))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: don't run with debug turned on in production!


SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 't')

ic("DEBUG: ", DEBUG)

SERVERNAME1 = os.environ.get('SERVERNAME1')
SERVERNAME2 = os.environ.get('SERVERNAME2')

ALLOWED_HOSTS = [h for h in ["127.0.0.1", SERVERNAME1, SERVERNAME2] if h]

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1',
    'http://localhost',
]
if SERVERNAME1:
    CSRF_TRUSTED_ORIGINS.extend([
        'https://' + SERVERNAME1,
        'http://' + SERVERNAME1,
    ])
if SERVERNAME2:
    CSRF_TRUSTED_ORIGINS.extend([
        'https://' + SERVERNAME2,
        'http://' + SERVERNAME2,
    ])

# CSRF Settings
CSRF_COOKIE_SECURE = False  # Set to False for HTTP
CSRF_COOKIE_SAMESITE = 'Lax'  # Allow cross-site requests in Lax mode
CSRF_USE_SESSIONS = False  # Store in cookie for easier JavaScript access
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access to the cookie
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'  # Django's default, matches our JavaScript
CSRF_COOKIE_NAME = 'csrftoken'  # Django's default, matches our JavaScript

# CORS Settings
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CSRF_TRUSTED_ORIGINS.extend(['http://localhost:*', 'http://127.0.0.1:*'])

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',

    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Your apps
    'sensors',
    'widget_tweaks',
    'crispy_forms',
    'crispy_bootstrap5',
    'corsheaders',
    'django_htmx',
    # ... other apps
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'sensors.middleware.TimezoneMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'sensors.middleware.ToastMiddleware',
]

ROOT_URLCONF = 'sensorplaces.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'sensors' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'sensors.context_processors.app_version_processor',
            ],
            'builtins': [
                'django.templatetags.static',
            ],
        },
    },
]

WSGI_APPLICATION = 'sensorplaces.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('SQLITE_FILE', BASE_DIR / 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR.parent, 'static_files')
STATICFILES_DIRS = [
    # os.path.join(BASE_DIR, 'static'), This directory does not exist and causes a warning.
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Media files (Uploaded files)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Maximum upload size (5MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Message settings - store in session but don't use for our toast system
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
MESSAGE_LEVEL = 40  # ERROR level only - we'll handle our own success/info messages

# Authentication settings
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

# Basic login URLs
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'

# Email settings for development (console backend)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Django-allauth configuration
ACCOUNT_LOGIN_METHODS = {'username', 'email'}  # Allow both username and email login

# Rate limiting settings
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/300s',  # 5 attempts per 300 seconds (5 minutes)
}

# Email verification settings
ACCOUNT_EMAIL_VERIFICATION = "optional"  # Change from "mandatory" to "optional"
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']  # New recommended way to specify required fields

# If you want to completely disable email verification for local users:
SOCIALACCOUNT_EMAIL_VERIFICATION = "mandatory"  # Keep strict verification for social accounts
SOCIALACCOUNT_EMAIL_REQUIRED = True  # Keep email required for social accounts

# Google OAuth2 settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

ACCOUNT_LOGOUT_ON_GET = True  # Add this to allow logout without confirmation
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True  # Add this to auto-login after email confirmation

# Security settings
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = None


# If you're using frames (like for map embedding)
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Security headers for HTTP
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Security Policy headers
# Browsers will ignore this on non-HTTPS sites, this will avoid the console warning.
# SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

if DEBUG:
    ic("disable SECURE_CROSS_ORIGIN_OPENER_POLICY")
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None
else:
    ic("enable SECURE_CROSS_ORIGIN_OPENER_POLICY")
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

SECURE_REFERRER_POLICY = 'same-origin'

APPEND_SLASH = True

# Debug Toolbar settings - requires DEBUG to be True
DEBUG_TOOLBAR = False
if DEBUG and os.environ.get('DEBUG_TOOLBAR', 'False').lower() == 'true':
    DEBUG_TOOLBAR = True

ic(DEBUG, DEBUG_TOOLBAR)

if DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    INSTALLED_APPS.append('template_profiler_panel')
    # Insert after AuthenticationMiddleware so we can check request.user
    try:
        auth_idx = MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')
        MIDDLEWARE.insert(auth_idx + 1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    except ValueError:
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

    # Internal IPS for Docker
    INTERNAL_IPS = [
        "127.0.0.1",
        "localhost",
    ]
    # Add the docker container IP
    import socket
    try:
        hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
        INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]
    except Exception:
        pass

    # Show toolbar only if user is logged in
    def show_toolbar(request):
        if request.user.is_authenticated:
            return True
        return False

    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': show_toolbar,
    }

    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
        'debug_toolbar.panels.profiling.ProfilingPanel',
        'template_profiler_panel.panels.template.TemplateProfilerPanel',
    ]


# SwitchBot settings
SWITCHBOT_TOKEN = os.environ.get("SWITCHBOT_TOKEN", None)
SWITCHBOT_SECRET = os.environ.get("SWITCHBOT_SECRET", None)

# Webhook Sniffer
WEBHOOK_SNIFFER = os.environ.get('WEBHOOK_SNIFFER', 'False').lower() in ('true', '1', 't')
ic(WEBHOOK_SNIFFER)
