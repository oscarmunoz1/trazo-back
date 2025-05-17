import os

from backend.settings.base import *
from decouple import config

ALLOWED_HOSTS = ("localhost", ".localhost", "192.168.1.3", "7172-167-60-250-132.ngrok-free.app")

# CSRF_TRUSTED_ORIGINS = [
#     "http://localhost:3000",
#     "http://app.localhost:3000",
#     "http://app.192.168.1.3:3000",
#     "http://localhost:8000",
# ]

CSRF_TRUSTED_ORIGINS = ["https://*.localhost", "http://app.localhost:3000", "https://7172-167-60-250-132.ngrok-free.app"]

CORS_ORIGIN_ALLOW_ALL = True

CORS_ORIGIN_WHITELIST = [
    # "http://localhost:3000",
    "http://app.localhost:3000",
    "http://app.192.168.1.3:3000",
    "https://7172-167-60-250-132.ngrok-free.app",
    # "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    # "http://localhost:3000",
    "http://app.localhost:3000",
    "http://app.192.168.1.3:3000",
    "https://7172-167-60-250-132.ngrok-free.app",
]

CSRF_COOKIE_DOMAIN = "localhost"


CSRF_COOKIE_SECURE = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
SERVER_EMAIL = os.environ.get("FROM_EMAIL_ADDRESS", "info@trazo.io")
DEFAULT_FROM_EMAIL = os.environ.get("FROM_EMAIL_ADDRESS", "info@trazo.io")

EMAIL_PORT = 1025
EMAIL_HOST = "localhost"
EMAIL_USE_TLS = False
EMAIL_HOST_USER = None
EMAIL_HOST_PASSWORD = None

# Use local filesystem in development
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Override Celery settings for development
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')

# Override Redis Cache settings for development
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config('REDIS_URL', default='redis://localhost:6379/1'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
