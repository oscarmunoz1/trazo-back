"""
Carbon Security Middleware

This middleware ensures that all carbon-related operations go through
comprehensive backend security validation and cannot be bypassed by
client-side manipulation.
"""

import json
import logging
import time
from typing import Dict, Any
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class CarbonSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to enforce security policies for carbon operations
    
    This middleware provides an additional layer of security that cannot
    be bypassed, ensuring all carbon operations meet security requirements.
    """
    
    # Critical endpoints that require enhanced security
    CRITICAL_ENDPOINTS = [
        '/api/carbon/entries/',
        '/api/carbon/offsets/',
        '/api/carbon/secure-offset/',
        '/api/carbon/purchases/',
        '/api/carbon/certificates/'
    ]
    
    # Security headers that must be present for critical operations
    REQUIRED_SECURITY_HEADERS = [
        'X-CSRFToken',
        'X-Requested-With'
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Process incoming requests for security validation"""
        
        # Skip security checks for non-carbon endpoints
        if not self._is_carbon_endpoint(request.path):
            return None
        
        # Skip for GET requests (read-only operations)
        if request.method == 'GET':
            return None
        
        # Apply enhanced security for critical endpoints
        if self._is_critical_endpoint(request.path):
            security_result = self._validate_critical_request(request)
            if security_result:
                return security_result
        
        # Apply rate limiting
        rate_limit_result = self._apply_rate_limiting(request)
        if rate_limit_result:
            return rate_limit_result
        
        # Validate request integrity
        integrity_result = self._validate_request_integrity(request)
        if integrity_result:
            return integrity_result
        
        return None
    
    def process_response(self, request, response):
        """Process responses to add security headers and logging"""
        
        if self._is_carbon_endpoint(request.path):
            # Add security headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            # Log critical operations
            if self._is_critical_endpoint(request.path) and request.method in ['POST', 'PUT', 'PATCH']:
                self._log_critical_operation(request, response)
        
        return response
    
    def _is_carbon_endpoint(self, path: str) -> bool:
        """Check if the endpoint is carbon-related"""
        carbon_paths = ['/api/carbon/', '/carbon/']
        return any(carbon_path in path for carbon_path in carbon_paths)
    
    def _is_critical_endpoint(self, path: str) -> bool:
        """Check if the endpoint is critical and requires enhanced security"""
        return any(critical_path in path for critical_path in self.CRITICAL_ENDPOINTS)
    
    def _validate_critical_request(self, request) -> JsonResponse:
        """Validate critical requests for security compliance"""
        
        # Check for required security headers in production
        if not settings.DEBUG:
            csrf_token = request.META.get('HTTP_X_CSRFTOKEN') or request.POST.get('csrfmiddlewaretoken')
            if not csrf_token:
                logger.warning(f"Missing CSRF token for critical request: {request.path}")
                return JsonResponse({
                    'error': 'Security validation failed',
                    'message': 'CSRF protection required',
                    'code': 'CSRF_MISSING'
                }, status=403)
            
            # Validate X-Requested-With header for AJAX requests
            if not request.META.get('HTTP_X_REQUESTED_WITH'):
                logger.warning(f"Missing X-Requested-With header: {request.path}")
                return JsonResponse({
                    'error': 'Security validation failed',
                    'message': 'Invalid request origin',
                    'code': 'INVALID_ORIGIN'
                }, status=403)
        
        # Validate user authentication for critical operations
        if not request.user or not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'message': 'You must be logged in to perform this action',
                'code': 'AUTH_REQUIRED'
            }, status=401)
        
        # Check for suspicious request patterns
        if self._detect_suspicious_patterns(request):
            return JsonResponse({
                'error': 'Security policy violation',
                'message': 'Suspicious activity detected',
                'code': 'SUSPICIOUS_ACTIVITY'
            }, status=403)
        
        return None
    
    def _apply_rate_limiting(self, request) -> JsonResponse:
        """Apply rate limiting to prevent abuse"""
        
        if not request.user or not request.user.is_authenticated:
            return None
        
        user_id = request.user.id
        endpoint = request.path
        method = request.method
        
        # Different limits for different operations
        limits = {
            'POST': {'requests': 30, 'window': 3600},  # 30 POST requests per hour
            'PUT': {'requests': 20, 'window': 3600},   # 20 PUT requests per hour
            'DELETE': {'requests': 10, 'window': 3600} # 10 DELETE requests per hour
        }
        
        if method in limits:
            limit_config = limits[method]
            cache_key = f"rate_limit:{user_id}:{method}:{endpoint}:{int(time.time() // limit_config['window'])}"
            
            current_requests = cache.get(cache_key, 0)
            if current_requests >= limit_config['requests']:
                logger.warning(f"Rate limit exceeded for user {user_id}: {method} {endpoint}")
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many {method} requests. Please wait before trying again.',
                    'retry_after': limit_config['window'],
                    'code': 'RATE_LIMIT_EXCEEDED'
                }, status=429)
            
            # Increment counter
            cache.set(cache_key, current_requests + 1, limit_config['window'])
        
        return None
    
    def _validate_request_integrity(self, request) -> JsonResponse:
        """Validate request integrity and detect tampering"""
        
        # Validate JSON payload for POST/PUT requests
        if request.method in ['POST', 'PUT', 'PATCH'] and request.content_type == 'application/json':
            try:
                if hasattr(request, 'body') and request.body:
                    json.loads(request.body)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in request body: {request.path}")
                return JsonResponse({
                    'error': 'Invalid request format',
                    'message': 'Request body must be valid JSON',
                    'code': 'INVALID_JSON'
                }, status=400)
        
        # Check for excessively large payloads
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                content_length = int(content_length)
                # 10MB limit for carbon operations
                max_size = 10 * 1024 * 1024
                if content_length > max_size:
                    logger.warning(f"Oversized request: {content_length} bytes from user {getattr(request.user, 'id', 'anonymous')}")
                    return JsonResponse({
                        'error': 'Request too large',
                        'message': f'Request size exceeds maximum allowed ({max_size} bytes)',
                        'code': 'REQUEST_TOO_LARGE'
                    }, status=413)
            except ValueError:
                pass
        
        return None
    
    def _detect_suspicious_patterns(self, request) -> bool:
        """Detect suspicious request patterns that might indicate attacks"""
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        user_id = request.user.id
        now = timezone.now()
        
        # Check for rapid-fire requests from same user
        rapid_requests_key = f"rapid_requests:{user_id}"
        rapid_count = cache.get(rapid_requests_key, 0)
        
        # More than 10 requests in 60 seconds is suspicious
        if rapid_count > 10:
            logger.warning(f"Rapid requests detected from user {user_id}")
            return True
        
        # Increment rapid request counter
        cache.set(rapid_requests_key, rapid_count + 1, 60)
        
        # Check for suspicious user agents
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        suspicious_agents = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python-requests', 'postman', 'insomnia'
        ]
        
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            logger.warning(f"Suspicious user agent: {user_agent} from user {user_id}")
            return True
        
        # Check for missing or suspicious referer
        referer = request.META.get('HTTP_REFERER', '')
        if not settings.DEBUG and not referer:
            # In production, require referer for critical operations
            if self._is_critical_endpoint(request.path):
                logger.warning(f"Missing referer for critical operation from user {user_id}")
                return True
        
        return False
    
    def _log_critical_operation(self, request, response):
        """Log critical operations for security monitoring"""
        
        user_id = getattr(request.user, 'id', 'anonymous')
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
        
        # Extract relevant data from request
        operation_data = {
            'user_id': user_id,
            'endpoint': request.path,
            'method': request.method,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': timezone.now().isoformat(),
            'response_status': response.status_code,
            'content_length': request.META.get('CONTENT_LENGTH', 0)
        }
        
        # Log successful operations
        if 200 <= response.status_code < 300:
            logger.info(f"Critical carbon operation successful: {json.dumps(operation_data)}")
        else:
            logger.warning(f"Critical carbon operation failed: {json.dumps(operation_data)}")
        
        # Store in cache for monitoring
        operations_key = f"critical_operations:{user_id}:{timezone.now().date()}"
        daily_operations = cache.get(operations_key, [])
        daily_operations.append(operation_data)
        
        # Keep only last 100 operations per day
        if len(daily_operations) > 100:
            daily_operations = daily_operations[-100:]
        
        cache.set(operations_key, daily_operations, 86400)  # 24 hours
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CarbonAuditMiddleware(MiddlewareMixin):
    """
    Middleware for comprehensive audit logging of carbon operations
    
    This middleware creates detailed audit trails for all carbon operations
    to ensure compliance and detect suspicious activities.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Start audit tracking for carbon requests"""
        
        if self._should_audit(request):
            request._audit_start_time = time.time()
            request._audit_data = {
                'method': request.method,
                'path': request.path,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                'content_type': request.content_type,
                'content_length': request.META.get('CONTENT_LENGTH', 0)
            }
        
        return None
    
    def process_response(self, request, response):
        """Complete audit logging for carbon responses"""
        
        if hasattr(request, '_audit_start_time'):
            processing_time = time.time() - request._audit_start_time
            
            audit_data = request._audit_data.copy()
            audit_data.update({
                'response_status': response.status_code,
                'processing_time_ms': round(processing_time * 1000, 2),
                'timestamp': timezone.now().isoformat()
            })
            
            # Log based on response status
            if 200 <= response.status_code < 300:
                logger.info(f"Carbon audit - Success: {json.dumps(audit_data)}")
            elif 400 <= response.status_code < 500:
                logger.warning(f"Carbon audit - Client Error: {json.dumps(audit_data)}")
            else:
                logger.error(f"Carbon audit - Server Error: {json.dumps(audit_data)}")
            
            # Store detailed audit for critical operations
            if self._is_critical_operation(request, response):
                self._store_detailed_audit(audit_data, request, response)
        
        return response
    
    def _should_audit(self, request) -> bool:
        """Determine if request should be audited"""
        carbon_paths = ['/api/carbon/', '/carbon/']
        return any(path in request.path for path in carbon_paths)
    
    def _is_critical_operation(self, request, response) -> bool:
        """Check if operation is critical and needs detailed auditing"""
        critical_paths = [
            '/api/carbon/entries/',
            '/api/carbon/offsets/',
            '/api/carbon/secure-offset/',
            '/api/carbon/purchases/'
        ]
        
        return (any(path in request.path for path in critical_paths) and 
                request.method in ['POST', 'PUT', 'PATCH', 'DELETE'])
    
    def _store_detailed_audit(self, audit_data: Dict[str, Any], request, response):
        """Store detailed audit information for critical operations"""
        
        # Store in database audit log if applicable
        try:
            from ..models import CarbonAuditLog
            
            if hasattr(request, 'user') and request.user.is_authenticated:
                CarbonAuditLog.objects.create(
                    user=request.user,
                    action='api_request',
                    details=json.dumps(audit_data),
                    ip_address=audit_data.get('ip_address')
                )
        except Exception as e:
            logger.error(f"Failed to store detailed audit: {str(e)}")
        
        # Store in cache for real-time monitoring
        detailed_key = f"detailed_audit:{audit_data.get('user_id', 'anonymous')}:{int(time.time())}"
        cache.set(detailed_key, audit_data, 3600)  # 1 hour
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip