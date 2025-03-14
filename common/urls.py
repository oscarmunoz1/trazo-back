from django.urls import path
from . import views

urlpatterns = [
    path('health-check/', views.health_check, name='health-check'),
    path('upload-urls/', views.get_upload_urls, name='get-upload-urls'),
]
