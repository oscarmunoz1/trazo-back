import os

from backend.settings.base import *
from decouple import config


ALLOWED_HOSTS = [
    "api.trazo.io",
    os.environ.get("LOAD_BALANCER_DNS", "localhost")
]


CSRF_TRUSTED_ORIGINS = [
    "https://*.trazo.io",
    "https://trazo.io",
    "https://api.trazo.io"
]

CORS_ORIGIN_ALLOW_ALL = True

CORS_ORIGIN_WHITELIST = ["https://app.trazo.io", "https://trazo.io"]
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = ["https://app.trazo.io", "https://trazo.io"]

CSRF_COOKIE_DOMAIN = "trazo.io"


CSRF_COOKIE_SECURE = True

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

# Override Celery settings for production
CELERY_BROKER_URL = config('REDIS_URL')
CELERY_RESULT_BACKEND = config('REDIS_URL')
CELERY_BROKER_USE_SSL = True
CELERY_REDIS_BACKEND_USE_SSL = True

# Override Redis Cache settings for production
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config('REDIS_URL'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SSL": True,
            "SSL_CERT_REQS": None,
        }
    }
}
