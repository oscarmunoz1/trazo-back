from .serializers import BasicUserSerializer
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from django.middleware import csrf

from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny
from rest_framework import status, generics
from rest_framework.decorators import (
    action,
    permission_classes as permission_classes_decorator,
    api_view,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from users.models import WorksIn, User
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .serializers import LoginSerializer, RegisterSerializer, MeSerializer
from rest_framework.views import APIView
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt

from django.conf import settings

from users.constants import SUPERUSER, PRODUCER, CONSUMER

import logging

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = BasicUserSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date_joined"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()

    def get_object(self):
        lookup_field_value = self.kwargs[self.lookup_field]
        obj = User.objects.get(id=lookup_field_value)
        self.check_object_permissions(self.request, obj)

        return obj

    def get_permissions(self):
        if self.action == "verify_email":
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def me(self, request, pk=None):
        serializer = MeSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def verify_email(self, request, pk=None):
        email = request.data.get("email")
        code = request.data.get("code")
        
        # Add logging for debugging
        logger.info(f"Verifying email: {email} with code: {code}")
        
        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not code:
            return Response(
                {"error": "Verification code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User with this email does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        if user.is_verified:
            return Response(
                {"error": "User is already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            verification = user.verification_code.last()
            if not verification or verification.code != code:
                return Response(
                    {"error": "Verification code is invalid"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            user.verification_code.all().delete()
            user.is_verified = True
            user.is_active = True
            user.save()
            
            return Response({"message": "Email verified successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            return Response(
                {"error": "An error occurred while verifying your email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def roles(self, request, pk=None):
        return Response(
            [{"id": role[0], "name": role[1]} for role in WorksIn.USER_ROLES]
        )


class LoginViewSet(viewsets.ModelViewSet, TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def get_subdomain(self, request):
        # First try to get from Origin header
        origin = request.headers.get('Origin')
        if origin:
            # Parse the origin URL
            from urllib.parse import urlparse
            parsed_uri = urlparse(origin)
            # Get the hostname (e.g., 'app.localhost:3000' or 'app.trazo.io')
            hostname = parsed_uri.netloc
            # Split and get first part
            subdomain = hostname.split('.')[0]
            return subdomain
        
        # Fallback to host header
        host = request.get_host()
        return host.split('.')[0] if '.' in host else None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        # Get user type and validate subdomain access
        user_type = serializer.validated_data.get('user_type')
        subdomain = self.get_subdomain(request)

        if subdomain == 'app':
            if user_type not in [SUPERUSER, PRODUCER]:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif subdomain == 'consumer':
            if user_type == CONSUMER:
                # Add additional consumer-specific validation if needed
                pass
        else:
            return Response(
                {"error": "Invalid domain"},
                status=status.HTTP_403_FORBIDDEN
            )

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        
        # Set secure cookie options
        cookie_options = {
            'secure': settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            'httponly': settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
            'samesite': settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
            'domain': settings.CSRF_COOKIE_DOMAIN
        }

        # Set cookies with improved security
        response.set_cookie(
            key="access",
            value=serializer.validated_data["access"],
            expires=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            **cookie_options
        )
        response.set_cookie(
            key="refresh",
            value=serializer.validated_data["refresh"],
            expires=settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
            **cookie_options
        )
        
        csrf.get_token(request)
        return response


class RegistrationViewSet(viewsets.ModelViewSet, TokenObtainPairView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        res = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        return Response(
            {
                "user": serializer.data,
                "refresh": res["refresh"],
                "token": res["access"],
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenRefreshView(TokenRefreshView):
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.COOKIES)
        try:
            if not serializer.is_valid():
                return Response({"error": "Token is invalid or expired"}, status=400)
            refresh_token = RefreshToken(serializer.validated_data["refresh"])
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        response.set_cookie(
            key="access",
            value=serializer.validated_data["access"],
            expires=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
            httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
            samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
        )
        response.set_cookie(
            key="refresh",
            value=serializer.validated_data["refresh"],
            expires=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
            httponly=settings.SIMPLE_JWT["AUTH_COOKIE_HTTP_ONLY"],
            samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
        )
        response.set_cookie(
            key="logged_in",
            value=True,
            expires=settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            secure=settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"],
            httponly=False,
            samesite=settings.SIMPLE_JWT["AUTH_COOKIE_SAMESITE"],
        )
        csrf.get_token(request)
        return response


@method_decorator(csrf_exempt, name='dispatch')
class APILogoutView(APIView):
    permission_classes = (IsAuthenticated,)
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        response = Response({"data": {"user": "ok"}}, status=status.HTTP_200_OK)
        response.delete_cookie(
            "access",
            domain=settings.SIMPLE_JWT["AUTH_COOKIE_DOMAIN"],
            path="/",
            samesite="None",
        )
        response.delete_cookie(
            "refresh",
            domain=settings.SIMPLE_JWT["AUTH_COOKIE_DOMAIN"],
            path="/",
            samesite="None",
        )
        response.delete_cookie(
            "logged_in",
            domain=settings.SIMPLE_JWT["AUTH_COOKIE_DOMAIN"],
            path="/",
            samesite="None",
        )
        return response
