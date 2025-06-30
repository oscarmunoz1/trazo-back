# cookieapp/authenticate.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings

from rest_framework.authentication import CSRFCheck
from rest_framework import exceptions


def enforce_csrf(request):
    def dummy_get_response(request):  # pragma: no cover
        return None

    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})

    if reason:
        raise exceptions.PermissionDenied("CSRF Failed: %s" % reason)


class CustomAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            raw_token = request.COOKIES.get(settings.SIMPLE_JWT["AUTH_COOKIE"]) or None
        else:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        
        # Only enforce CSRF for state-changing operations (POST, PUT, PATCH, DELETE)
        # GET requests are safe and don't need CSRF protection
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Skip CSRF check for certain safe endpoints
            safe_paths = ['/auth/logout/', '/auth/refresh/']
            if request.path not in safe_paths:
                try:
                    enforce_csrf(request)
                except exceptions.PermissionDenied:
                    # In development, be more lenient with CSRF
                    if not settings.DEBUG:
                        raise
                    # Log the CSRF issue but don't block in development
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"CSRF check failed for {request.path} - allowing in development mode")
            
        return self.get_user(validated_token), validated_token
