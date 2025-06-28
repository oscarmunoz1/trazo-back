from rest_framework.routers import SimpleRouter
from .views import (
    UserViewSet,
    LoginViewSet,
    RegistrationViewSet,
    CustomTokenRefreshView,
    APILogoutView,
)
from .social_auth import SocialAuthView
from rest_framework_simplejwt.views import TokenRefreshView
from django.urls import path

routes = SimpleRouter()

# AUTHENTICATION
routes.register(r"auth/login", LoginViewSet, basename="auth-login")
routes.register(r"auth/register", RegistrationViewSet, basename="auth-register")

# USER
routes.register(r"users", UserViewSet, basename="user")


urlpatterns = [
    *routes.urls,
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", APILogoutView.as_view(), name="logout"),
    path("auth/social/", SocialAuthView.as_view(), name="social_auth"),
]
