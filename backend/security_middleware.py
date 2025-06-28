"""
Security middleware for logging authentication failures and rate limit violations
"""
import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden
from django_ratelimit.exceptions import Ratelimited

logger = logging.getLogger('security')


class SecurityLoggingMiddleware(MiddlewareMixin):
    """Middleware to log security events"""
    
    def process_request(self, request):
        """Check for suspicious request patterns"""
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        user = getattr(request, 'user', None)
        username = user.username if user and user.is_authenticated else 'Anonymous'
        
        # Log suspicious POST requests with large payloads
        if (request.method == 'POST' and 
            hasattr(request, 'body') and 
            len(request.body) > 1024 * 1024):  # 1MB
            logger.warning(
                f"Large POST request - IP: {client_ip}, User: {username}, "
                f"Path: {request.path}, Size: {len(request.body)} bytes, "
                f"User-Agent: {user_agent}"
            )
        
        return None
    
    def process_exception(self, request, exception):
        """Log security-related exceptions"""
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        user = getattr(request, 'user', None)
        username = user.username if user and user.is_authenticated else 'Anonymous'
        
        if isinstance(exception, Ratelimited):
            # Log rate limit violations
            logger.warning(
                f"Rate limit exceeded - IP: {client_ip}, User: {username}, "
                f"Path: {request.path}, Method: {request.method}, "
                f"User-Agent: {user_agent}"
            )
            
            # Return a custom response for rate limiting
            return HttpResponseForbidden(
                json.dumps({
                    'error': 'Rate limit exceeded',
                    'detail': 'Too many requests. Please try again later.'
                }),
                content_type='application/json'
            )
        
        # Let other exceptions be handled normally
        return None
    
    def process_response(self, request, response):
        """Log authentication failures"""
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        user = getattr(request, 'user', None)
        username = user.username if user and user.is_authenticated else 'Anonymous'
        
        # Log 401 Unauthorized responses
        if response.status_code == 401:
            logger.warning(
                f"Authentication failed - IP: {client_ip}, User: {username}, "
                f"Path: {request.path}, Method: {request.method}, "
                f"User-Agent: {user_agent}"
            )
        
        # Log 403 Forbidden responses
        elif response.status_code == 403:
            logger.warning(
                f"Access denied - IP: {client_ip}, User: {username}, "
                f"Path: {request.path}, Method: {request.method}, "
                f"User-Agent: {user_agent}"
            )
        
        
        return response
    
    def get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain (original client)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CSRFSecurityMiddleware(MiddlewareMixin):
    """Additional CSRF security checks"""
    
    def process_request(self, request):
        """Check for suspicious CSRF patterns"""
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        
        # Log requests without proper Referer headers for state-changing operations
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            referer = request.META.get('HTTP_REFERER')
            origin = request.META.get('HTTP_ORIGIN')
            
            if not referer and not origin:
                logger.warning(
                    f"Suspicious request without Referer/Origin - IP: {client_ip}, "
                    f"Path: {request.path}, Method: {request.method}, "
                    f"User-Agent: {user_agent}"
                )
        
        return None
    
    def get_client_ip(self, request):
        """Get the real client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip