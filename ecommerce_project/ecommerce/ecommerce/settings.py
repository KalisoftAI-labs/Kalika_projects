import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set in environment variables")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("SECRET_KEY must be at least 50 characters long")

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

#ALLOWED_HOSTS = ['localhost', '127.0.0.1']
ALLOWED_HOSTS = [
    'www.kalikaindia.com', 
    'kalikaindia.com', 
    'localhost', 
    '127.0.0.1',
    '34.226.85.194',  # EC2 public IP
    '172.31.17.182'   # EC2 private IP
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'catalog.apps.CatalogConfig',
    'accounts.apps.AccountsConfig',
    'cart.apps.CartConfig',
    'crispy_forms',
    'crispy_bootstrap4',
    'punchout',
    'fastapi_app',
    
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'ecommerce.middleware.security_middleware.SecurityMiddleware',  # Custom IP blocking
    'ecommerce.middleware.security_middleware.RateLimitMiddleware',  # Rate limiting
    'django.contrib.sessions.middleware.SessionMiddleware',
    'ecommerce.middleware.security_middleware.PunchoutSessionMiddleware',  # PunchOut session handling (MUST be AFTER SessionMiddleware)
    'ecommerce.middleware.security_middleware.PunchoutCSPMiddleware',  # PunchOut iframe support
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ecommerce.urls'

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
                'catalog.context_processors.categories',
                'catalog.context_processors.cart_item_count',
                'catalog.context_processors.punchout_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecommerce.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'ecom_prod_catalog'),
        'USER': os.getenv('DB_USER', 'vikas'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'kalika1667'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_USER_MODEL = 'accounts.CustomUser'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'fastapi_app/static')]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "mediafiles"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_ALLOWED_TEMPLATE_PACKS = ('bootstrap4',)

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = 'us-east-1'
AWS_S3_BUCKET_NAME = 'kalika-ecom'

# =============================================================================
# SESSION CONFIGURATION - Ariba PunchOut Optimized
# =============================================================================
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 3600  # 1 hour for PunchOut sessions
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True  # CRITICAL: Ensure session persists on every request
SESSION_COOKIE_DOMAIN = '.kalikaindia.com'  # CRITICAL: Allow session cookies across www/non-www variants

# Caching Configuration
# Using local-memory caching (for single-server setup)
# For production with multiple servers, use Redis or Memcached
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 5000,  # Store up to 5000 cached items
        }
    },
    'product_images': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'product-image-cache',
        'TIMEOUT': 3600,  # Cache S3 URLs for 1 hour
        'OPTIONS': {
            'MAX_ENTRIES': 10000,
        }
    }
}

# =============================================================================
# SAP ARIBA PUNCHOUT CONFIGURATION
# =============================================================================
PUNCHOUT_SUPPLIER_DUNS = os.getenv('PUNCHOUT_SUPPLIER_DUNS')
PUNCHOUT_ANID = os.getenv('PUNCHOUT_ANID')  # Required: Your Ariba Network ID
PUNCHOUT_SHARED_SECRET = os.getenv('PUNCHOUT_SHARED_SECRET')  # Optional for default auth
# Note: SharedSecret validation is optional in views.py for default authentication
PUNCHOUT_RETURN_URL = os.getenv('PUNCHOUT_RETURN_URL', 'https://ariba.com/BUYER/po/')
ARIBA_NETWORK_ID = os.getenv('ARIBA_NETWORK_ID')
ARIBA_ENDPOINT = 'https://open.ariba.com/punchout/cxml/setup'  # Production endpoint

# --- Security Settings ---
# For production deployment, these MUST be enabled
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Set to True for production with HTTPS
SECURE_SSL_REDIRECT = True  # Enable in production
SESSION_COOKIE_SECURE = True  # Cookies only over HTTPS
CSRF_COOKIE_SECURE = True     # CSRF cookies only over HTTPS

# CSRF Settings for PunchOut Integration
# =============================================================================
# SAP ARIBA TRUSTED ORIGINS (Production + Test Environments)
# =============================================================================
CSRF_TRUSTED_ORIGINS = [
    'https://kalikaindia.com',
    'https://www.kalikaindia.com',
    'https://service.ariba.com',
    'https://open.ariba.com',
    'https://ariba.com',
    'https://test.ariba.com',
    'https://*.ariba.com',
    'https://*.sap.com',
    'https://*.aribanetwork.com',
]

# =============================================================================
# CRITICAL: ARIBA IFRAME + CROSS-SITE COMPATIBILITY
# =============================================================================
CSRF_COOKIE_SAMESITE = 'None'  # Required for cross-site iframe embedding
SESSION_COOKIE_SAMESITE = 'None'  # Required for cross-site iframe embedding
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript access to CSRF token in iframe context

# Additional security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = ''  # EMPTY = Allows Ariba to embed in iframes (overridden by CSP middleware)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
        'security_file': {
            'level': 'ERROR',  # Only log critical errors
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 2,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {  # Root logger - catches everything not explicitly configured
            'handlers': ['null'],
            'level': 'ERROR',
        },
        'django': {
            'handlers': ['null'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['null'],  # Suppress 404 and other request warnings
            'level': 'CRITICAL',  # Only critical errors
            'propagate': False,
        },
        'django.server': {
            'handlers': ['null'],  # Suppress server 404 warnings
            'level': 'CRITICAL',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file'],
            'level': 'ERROR',  # Only actual errors
            'propagate': False,
        },
        'ecommerce.middleware': {
            'handlers': ['null'],  # Suppress middleware warnings
            'level': 'CRITICAL',
            'propagate': False,
        },
    },
}