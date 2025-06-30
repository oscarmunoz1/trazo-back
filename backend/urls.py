"""backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from common.views import health_check

@ensure_csrf_cookie
def get_csrf_token(request):
    """
    Global CSRF token endpoint.
    
    This endpoint ensures the CSRF cookie is set and returns the token
    for use in AJAX requests across the entire application.
    """
    return JsonResponse({
        'csrf_token': get_token(request),
        'message': 'CSRF token set successfully'
    })

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # Global CSRF token endpoint
    path("api/csrf-token/", get_csrf_token, name="csrf_token"),
    path(
        "",
        include(
            ("users.urls"),
        ),
    ),
    path("", include("company.urls")),
    path("", include("product.urls")),
    path("", include("history.urls")),
    path("", include("reviews.urls")),
    path("", include("common.urls")),
    path("", include("subscriptions.urls")),
    path('carbon/', include('carbon.urls')),
    path('support/', include('support.urls')),
    path('education/', include('education.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_URL)
