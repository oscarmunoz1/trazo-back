# Production Settings Override

import os
from decouple import config
from backend.settings.base import *
import dj_database_url

# Explicitly disable debug in production
DEBUG = False

# Validate SECRET_KEY for production
SECRET_KEY = config('SECRET_KEY')
if not SECRET_KEY or len(SECRET_KEY) < 50:
    raise ValueError("Production requires a strong SECRET_KEY with at least 50 characters")

# Database Configuration for Railway
DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL', default='sqlite:///db.sqlite3')
    )
}

ALLOWED_HOSTS = [
    "api.trazo.io",
    "api-staging.trazo.io",
    os.environ.get("LOAD_BALANCER_DNS", "localhost"),
    os.environ.get("RAILWAY_STATIC_URL", "localhost"),
    "*.railway.app",
    "localhost"
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.trazo.io",
    "https://trazo.io",
    "https://api.trazo.io",
    "https://api-staging.trazo.io"
]

CORS_ORIGIN_ALLOW_ALL = True

CORS_ORIGIN_WHITELIST = [
    "https://app.trazo.io", 
    "https://trazo.io",
    "https://app-staging.trazo.io",
    "https://staging.trazo.io"
]
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "https://app.trazo.io", 
    "https://trazo.io",
    "https://app-staging.trazo.io",
    "https://staging.trazo.io"
]

CSRF_COOKIE_DOMAIN = "trazo.io"

CSRF_COOKIE_SECURE = True

# Security Headers for Production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
SERVER_EMAIL = os.environ.get("FROM_EMAIL_ADDRESS", "info@trazo.io")
DEFAULT_FROM_EMAIL = config("FROM_EMAIL_ADDRESS", "info@trazo.io")

SENDGRID_API_KEY = config("SENDGRID_API_KEY", default=None)

EMAIL_HOST = config("EMAIL_HOST", default="smtp.sendgrid.net")
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
EMAIL_PORT = os.environ.get("EMAIL_PORT", 587)
EMAIL_USE_TLS = False if os.environ.get("EMAIL_DISABLE_TLS") == "True" else True

# Use S3 in production
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Redis Configuration - Remove SSL for Railway internal Redis
REDIS_URL = config('REDIS_URL', default=None)

# Override Celery settings for production - No SSL for Railway internal Redis
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    # Remove SSL requirements for Railway internal Redis
    CELERY_BROKER_USE_SSL = False
    CELERY_REDIS_BACKEND_USE_SSL = False
else:
    # Disable Celery if no Redis
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_STORE_EAGER_RESULT = True

# Override Redis Cache settings for production - No SSL for Railway internal Redis
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                # Remove SSL requirements for Railway internal Redis
                "SSL": False,
                "CONNECTION_POOL_KWARGS": {"retry_on_timeout": True},
            }
        }
    }
else:
    # Fallback to local memory cache if no Redis
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# USDA API Configuration - Use environment variables for security
USDA_NASS_API_KEY = os.environ.get('USDA_NASS_API_KEY', None)
USDA_ERS_API_KEY = os.environ.get('USDA_ERS_API_KEY', None)
USDA_FOODDATA_API_KEY = os.environ.get('USDA_FOODDATA_API_KEY', None)

# API Attribution (required by NASS Terms of Service)
USDA_API_ATTRIBUTION = "This product uses the NASS API but is not endorsed or certified by NASS."

# John Deere API Configuration
JOHN_DEERE_CLIENT_ID = os.environ.get('JOHN_DEERE_CLIENT_ID', None)
JOHN_DEERE_CLIENT_SECRET = os.environ.get('JOHN_DEERE_CLIENT_SECRET', None)
JOHN_DEERE_REDIRECT_URI = os.environ.get('JOHN_DEERE_REDIRECT_URI', 'https://api.trazo.io/carbon/john-deere/callback/')
JOHN_DEERE_USE_SANDBOX = os.environ.get('JOHN_DEERE_USE_SANDBOX', 'False').lower() == 'true'

# Weather API Configuration
NOAA_API_BASE_URL = "https://api.weather.gov"
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', None)
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

# Weather alert thresholds (can be customized per establishment)
WEATHER_ALERT_THRESHOLDS = {
    'high_temp': 85,  # Fahrenheit
    'low_temp': 35,   # Fahrenheit
    'high_wind': 20,  # mph
    'low_humidity': 30,  # percentage
    'high_humidity': 85  # percentage
}

# Blockchain Configuration - REQUIRED in production
BLOCKCHAIN_ENABLED = config('BLOCKCHAIN_ENABLED', default=True, cast=bool)
POLYGON_RPC_URL = config('POLYGON_RPC_URL', default=None)
CARBON_CONTRACT_ADDRESS = config('CARBON_CONTRACT_ADDRESS', default=None)
BLOCKCHAIN_PRIVATE_KEY = config('BLOCKCHAIN_PRIVATE_KEY', default=None)
POLYGON_EXPLORER_URL = config('POLYGON_EXPLORER_URL', default='https://polygonscan.com')

# Force blockchain verification configuration
FORCE_BLOCKCHAIN_VERIFICATION = config('FORCE_BLOCKCHAIN_VERIFICATION', default=False, cast=bool)

# Production blockchain validation
if BLOCKCHAIN_ENABLED:
    required_blockchain_vars = [
        ('POLYGON_RPC_URL', POLYGON_RPC_URL),
        ('CARBON_CONTRACT_ADDRESS', CARBON_CONTRACT_ADDRESS),
        ('BLOCKCHAIN_PRIVATE_KEY', BLOCKCHAIN_PRIVATE_KEY)
    ]
    
    missing_vars = [var for var, value in required_blockchain_vars if not value]
    if missing_vars:
        # For staging, log warning instead of failing
        environment = config('ENVIRONMENT', default='production')
        if environment == 'staging':
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Staging blockchain is enabled but missing environment variables: {', '.join(missing_vars)}. "
                f"Blockchain features may not work properly."
            )
        else:
            raise ValueError(
                f"Production blockchain is enabled but missing required environment variables: {', '.join(missing_vars)}. "
                f"Set these variables or set BLOCKCHAIN_ENABLED=False to disable blockchain features."
            )

# ICR (International Carbon Registry) Configuration
ICR_API_KEY = config('ICR_API_KEY', default=None)
ICR_PRODUCTION_URL = config('ICR_PRODUCTION_URL', default='https://api.carbonregistry.com')
USE_ICR_SANDBOX = config('USE_ICR_SANDBOX', default=False, cast=bool)  # Production uses real API

# AWS Services Configuration
AWS_SERVICES_ENABLED = config('AWS_SERVICES_ENABLED', default=True, cast=bool)
FORCE_AWS_KEY_MANAGEMENT = config('FORCE_AWS_KEY_MANAGEMENT', default=False, cast=bool)
ENVIRONMENT = config('ENVIRONMENT', default='production')
