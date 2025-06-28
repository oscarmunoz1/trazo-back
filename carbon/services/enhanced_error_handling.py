"""
Enhanced Error Handling and Fallback Mechanisms for Trazo
Provides comprehensive error handling, retry logic, and fallback mechanisms
"""

import logging
import time
import json
import traceback
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
import asyncio
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"           # Minor issues, continue operation
    MEDIUM = "medium"     # Significant issues, degraded operation
    HIGH = "high"         # Critical issues, limited operation
    CRITICAL = "critical" # System failure, emergency fallback


class FallbackStrategy(Enum):
    """Fallback strategy types"""
    CACHE = "cache"           # Use cached data
    DEFAULT = "default"       # Use default values
    ALTERNATIVE = "alternative"  # Use alternative service/method
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Reduce functionality
    FAIL_SAFE = "fail_safe"   # Safe mode operation


@dataclass
class ErrorContext:
    """Context information for error handling"""
    operation: str
    component: str
    timestamp: datetime
    severity: ErrorSeverity
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms"""
    max_attempts: int = 3
    base_delay: float = 1.0      # Base delay in seconds
    max_delay: float = 60.0      # Maximum delay between retries
    exponential_backoff: bool = True
    jitter: bool = True          # Add random jitter to prevent thundering herd
    retry_on_exceptions: List[type] = field(default_factory=lambda: [Exception])
    stop_on_exceptions: List[type] = field(default_factory=list)


@dataclass
class FallbackConfig:
    """Configuration for fallback mechanisms"""
    strategy: FallbackStrategy
    cache_ttl: int = 3600        # Cache TTL for fallback data
    timeout: float = 30.0        # Timeout for fallback operations
    fallback_data: Optional[Dict[str, Any]] = None
    alternative_service: Optional[str] = None


class EnhancedErrorHandler:
    """
    Comprehensive error handling with intelligent retry and fallback mechanisms
    """
    
    def __init__(self):
        self.error_stats = {
            'total_errors': 0,
            'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'errors_by_component': {},
            'successful_recoveries': 0,
            'failed_recoveries': 0
        }
        
        # Error patterns for classification
        self.error_patterns = {
            'network': ['timeout', 'connection', 'network', 'unreachable'],
            'authentication': ['auth', 'unauthorized', 'forbidden', 'token'],
            'rate_limit': ['rate limit', 'too many requests', '429'],
            'validation': ['validation', 'invalid', 'format', 'schema'],
            'resource': ['not found', '404', 'missing', 'unavailable'],
            'server': ['500', 'internal server', 'server error', 'service unavailable']
        }
        
        # Default fallback configurations by component
        self.default_fallback_configs = {
            'usda_api': FallbackConfig(
                strategy=FallbackStrategy.CACHE,
                cache_ttl=7200,
                fallback_data={'data': [], 'source': 'fallback'}
            ),
            'blockchain': FallbackConfig(
                strategy=FallbackStrategy.GRACEFUL_DEGRADATION,
                timeout=60.0,
                fallback_data={'simulated': True, 'hash': '0x' + '0' * 64}
            ),
            'carbon_calculation': FallbackConfig(
                strategy=FallbackStrategy.DEFAULT,
                fallback_data={
                    'carbon_intensity': 1.0,
                    'confidence_level': 'low',
                    'source': 'fallback_estimate'
                }
            ),
            'weather_api': FallbackConfig(
                strategy=FallbackStrategy.CACHE,
                cache_ttl=1800,
                fallback_data={'temperature': 20, 'humidity': 50, 'source': 'fallback'}
            )
        }
        
        logger.info("EnhancedErrorHandler initialized")
    
    def classify_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorSeverity:
        """
        Classify error severity based on error type and context
        
        Args:
            error: Exception to classify
            context: Additional context for classification
            
        Returns:
            Error severity level
        """
        try:
            error_message = str(error).lower()
            error_type = type(error).__name__
            
            # Critical errors
            if any(keyword in error_message for keyword in ['critical', 'fatal', 'security']):
                return ErrorSeverity.CRITICAL
            
            # High severity errors
            if any(keyword in error_message for keyword in ['database', 'corruption', 'integrity']):
                return ErrorSeverity.HIGH
            
            # Medium severity errors
            if any(keyword in error_message for keyword in ['timeout', 'unavailable', 'failed']):
                return ErrorSeverity.MEDIUM
            
            # Network and temporary errors are usually low severity
            if any(keyword in error_message for keyword in ['network', 'connection', 'temporary']):
                return ErrorSeverity.LOW
            
            # Default classification based on exception type
            critical_exceptions = ['SystemExit', 'KeyboardInterrupt', 'MemoryError']
            high_exceptions = ['PermissionError', 'FileNotFoundError', 'ImportError']
            medium_exceptions = ['ValueError', 'TypeError', 'AttributeError']
            
            if error_type in critical_exceptions:
                return ErrorSeverity.CRITICAL
            elif error_type in high_exceptions:
                return ErrorSeverity.HIGH
            elif error_type in medium_exceptions:
                return ErrorSeverity.MEDIUM
            else:
                return ErrorSeverity.LOW
                
        except Exception as e:
            logger.error(f"Error classifying error severity: {e}")
            return ErrorSeverity.MEDIUM  # Safe default
    
    def create_error_context(self, 
                           operation: str,
                           component: str,
                           error: Exception,
                           **kwargs) -> ErrorContext:
        """
        Create comprehensive error context
        
        Args:
            operation: Operation that failed
            component: Component where error occurred
            error: Exception that occurred
            **kwargs: Additional context data
            
        Returns:
            Error context object
        """
        severity = self.classify_error(error, kwargs)
        
        return ErrorContext(
            operation=operation,
            component=component,
            timestamp=timezone.now(),
            severity=severity,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            request_id=kwargs.get('request_id'),
            user_id=kwargs.get('user_id'),
            additional_data=kwargs
        )
    
    def log_error(self, error_context: ErrorContext):
        """
        Log error with appropriate level and structured data
        
        Args:
            error_context: Error context to log
        """
        try:
            # Update statistics
            self.error_stats['total_errors'] += 1
            self.error_stats['errors_by_severity'][error_context.severity.value] += 1
            
            component = error_context.component
            if component not in self.error_stats['errors_by_component']:
                self.error_stats['errors_by_component'][component] = 0
            self.error_stats['errors_by_component'][component] += 1
            
            # Create structured log data
            log_data = {
                'operation': error_context.operation,
                'component': error_context.component,
                'error_type': error_context.error_type,
                'severity': error_context.severity.value,
                'timestamp': error_context.timestamp.isoformat(),
                'request_id': error_context.request_id,
                'user_id': error_context.user_id
            }
            
            # Log at appropriate level
            if error_context.severity == ErrorSeverity.CRITICAL:
                logger.critical(f"CRITICAL ERROR in {component}.{error_context.operation}: {error_context.error_message}", 
                              extra=log_data)
            elif error_context.severity == ErrorSeverity.HIGH:
                logger.error(f"HIGH severity error in {component}.{error_context.operation}: {error_context.error_message}", 
                           extra=log_data)
            elif error_context.severity == ErrorSeverity.MEDIUM:
                logger.warning(f"MEDIUM severity error in {component}.{error_context.operation}: {error_context.error_message}", 
                             extra=log_data)
            else:
                logger.info(f"LOW severity error in {component}.{error_context.operation}: {error_context.error_message}", 
                          extra=log_data)
            
            # Log stack trace for high/critical errors
            if error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] and error_context.stack_trace:
                logger.error(f"Stack trace for {component}.{error_context.operation}:\n{error_context.stack_trace}")
                
        except Exception as e:
            # Fallback logging if structured logging fails
            logger.error(f"Failed to log error properly: {e}. Original error: {error_context.error_message}")
    
    def get_fallback_data(self, component: str, operation: str, error_context: ErrorContext) -> Any:
        """
        Get fallback data based on component and operation
        
        Args:
            component: Component name
            operation: Operation name
            error_context: Error context
            
        Returns:
            Fallback data or None
        """
        try:
            fallback_config = self.default_fallback_configs.get(component)
            if not fallback_config:
                logger.warning(f"No fallback configuration for component: {component}")
                return None
            
            if fallback_config.strategy == FallbackStrategy.CACHE:
                # Try to get cached data
                cache_key = f"fallback_{component}_{operation}"
                cached_data = cache.get(cache_key)
                
                if cached_data:
                    logger.info(f"Using cached fallback data for {component}.{operation}")
                    return cached_data
                
                # Fall back to default data
                if fallback_config.fallback_data:
                    logger.info(f"Using default fallback data for {component}.{operation}")
                    return fallback_config.fallback_data
            
            elif fallback_config.strategy == FallbackStrategy.DEFAULT:
                logger.info(f"Using default fallback for {component}.{operation}")
                return fallback_config.fallback_data
            
            elif fallback_config.strategy == FallbackStrategy.GRACEFUL_DEGRADATION:
                logger.info(f"Graceful degradation for {component}.{operation}")
                degraded_data = fallback_config.fallback_data.copy() if fallback_config.fallback_data else {}
                degraded_data['degraded_mode'] = True
                degraded_data['timestamp'] = timezone.now().isoformat()
                return degraded_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get fallback data: {e}")
            return None
    
    def retry_with_backoff(self, 
                          func: Callable,
                          config: RetryConfig,
                          *args,
                          **kwargs) -> Any:
        """
        Retry function with exponential backoff and jitter
        
        Args:
            func: Function to retry
            config: Retry configuration
            *args, **kwargs: Arguments for the function
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # Check if we should stop retrying
                if any(isinstance(e, exc_type) for exc_type in config.stop_on_exceptions):
                    logger.warning(f"Stopping retries due to {type(e).__name__}: {e}")
                    raise e
                
                # Check if we should retry
                if not any(isinstance(e, exc_type) for exc_type in config.retry_on_exceptions):
                    logger.warning(f"Not retrying for {type(e).__name__}: {e}")
                    raise e
                
                # Calculate delay for next attempt
                if attempt < config.max_attempts - 1:  # Don't delay after last attempt
                    delay = config.base_delay
                    
                    if config.exponential_backoff:
                        delay = min(config.base_delay * (2 ** attempt), config.max_delay)
                    
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
                    
                    logger.info(f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. Retrying in {delay:.2f}s")
                    time.sleep(delay)
                else:
                    logger.error(f"All {config.max_attempts} attempts failed. Last error: {e}")
        
        # All retries failed
        if last_exception:
            raise last_exception
    
    def handle_with_fallback(self, 
                           func: Callable,
                           component: str,
                           operation: str,
                           retry_config: Optional[RetryConfig] = None,
                           fallback_config: Optional[FallbackConfig] = None,
                           *args,
                           **kwargs) -> Any:
        """
        Execute function with comprehensive error handling and fallback
        
        Args:
            func: Function to execute
            component: Component name
            operation: Operation name
            retry_config: Retry configuration
            fallback_config: Fallback configuration
            *args, **kwargs: Function arguments
            
        Returns:
            Function result or fallback data
        """
        # Use default configs if not provided
        if retry_config is None:
            retry_config = RetryConfig()
        
        if fallback_config is None:
            fallback_config = self.default_fallback_configs.get(component, FallbackConfig(FallbackStrategy.DEFAULT))
        
        try:
            # Try with retries
            return self.retry_with_backoff(func, retry_config, *args, **kwargs)
            
        except Exception as e:
            # Create error context
            error_context = self.create_error_context(operation, component, e, **kwargs)
            
            # Log error
            self.log_error(error_context)
            
            # Try fallback
            try:
                fallback_data = self.get_fallback_data(component, operation, error_context)
                
                if fallback_data is not None:
                    self.error_stats['successful_recoveries'] += 1
                    logger.info(f"Successfully recovered using fallback for {component}.{operation}")
                    return fallback_data
                else:
                    self.error_stats['failed_recoveries'] += 1
                    logger.error(f"No fallback available for {component}.{operation}")
                    raise e
                    
            except Exception as fallback_error:
                self.error_stats['failed_recoveries'] += 1
                logger.error(f"Fallback failed for {component}.{operation}: {fallback_error}")
                raise e  # Raise original error, not fallback error
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive error handling statistics
        
        Returns:
            Error handling statistics
        """
        total_errors = self.error_stats['total_errors']
        total_recoveries = self.error_stats['successful_recoveries'] + self.error_stats['failed_recoveries']
        
        recovery_rate = (self.error_stats['successful_recoveries'] / total_recoveries * 100 
                        if total_recoveries > 0 else 0)
        
        return {
            'total_errors': total_errors,
            'errors_by_severity': self.error_stats['errors_by_severity'],
            'errors_by_component': self.error_stats['errors_by_component'],
            'recovery_attempts': total_recoveries,
            'successful_recoveries': self.error_stats['successful_recoveries'],
            'failed_recoveries': self.error_stats['failed_recoveries'],
            'recovery_rate_percent': round(recovery_rate, 2),
            'error_handling_features': {
                'automatic_retry': True,
                'exponential_backoff': True,
                'circuit_breaker_integration': True,
                'fallback_mechanisms': True,
                'error_classification': True,
                'structured_logging': True
            }
        }


# Global error handler instance
error_handler = EnhancedErrorHandler()


def with_error_handling(component: str, 
                       operation: str = None,
                       retry_config: RetryConfig = None,
                       fallback_config: FallbackConfig = None):
    """
    Decorator for automatic error handling with retry and fallback
    
    Args:
        component: Component name
        operation: Operation name (defaults to function name)
        retry_config: Retry configuration
        fallback_config: Fallback configuration
        
    Usage:
        @with_error_handling('usda_api', 'fetch_yield_data')
        def fetch_usda_yield_data(crop, state):
            # API call here
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation or func.__name__
            return error_handler.handle_with_fallback(
                func, component, op_name, retry_config, fallback_config, *args, **kwargs
            )
        return wrapper
    return decorator


def safe_execute(func: Callable, 
                component: str,
                operation: str = None,
                default_return: Any = None,
                log_errors: bool = True) -> Any:
    """
    Safely execute a function with basic error handling
    
    Args:
        func: Function to execute
        component: Component name
        operation: Operation name
        default_return: Default return value on error
        log_errors: Whether to log errors
        
    Returns:
        Function result or default value
    """
    try:
        return func()
    except Exception as e:
        if log_errors:
            error_context = error_handler.create_error_context(
                operation or func.__name__, component, e
            )
            error_handler.log_error(error_context)
        return default_return


# Specialized error handlers for Trazo components

class USDAAPIErrorHandler:
    """Specialized error handler for USDA API operations"""
    
    @staticmethod
    def handle_api_error(operation: str, error: Exception, crop_type: str = None, state: str = None):
        """Handle USDA API specific errors with context"""
        context = {'crop_type': crop_type, 'state': state}
        error_context = error_handler.create_error_context(operation, 'usda_api', error, **context)
        error_handler.log_error(error_context)
        
        # Return appropriate fallback data
        return error_handler.get_fallback_data('usda_api', operation, error_context)


class BlockchainErrorHandler:
    """Specialized error handler for blockchain operations"""
    
    @staticmethod
    def handle_transaction_error(operation: str, error: Exception, tx_data: Dict = None):
        """Handle blockchain transaction errors with gas optimization context"""
        context = {'transaction_data': tx_data}
        error_context = error_handler.create_error_context(operation, 'blockchain', error, **context)
        error_handler.log_error(error_context)
        
        # For blockchain errors, use graceful degradation
        return error_handler.get_fallback_data('blockchain', operation, error_context)


class CarbonCalculationErrorHandler:
    """Specialized error handler for carbon calculation operations"""
    
    @staticmethod
    def handle_calculation_error(operation: str, error: Exception, inputs: Dict = None):
        """Handle carbon calculation errors with input context"""
        context = {'calculation_inputs': inputs}
        error_context = error_handler.create_error_context(operation, 'carbon_calculation', error, **context)
        error_handler.log_error(error_context)
        
        # Return conservative fallback estimates
        return error_handler.get_fallback_data('carbon_calculation', operation, error_context)


# Utility functions for monitoring and alerting

def get_system_health_status() -> Dict[str, Any]:
    """
    Get overall system health based on error patterns
    
    Returns:
        System health status
    """
    stats = error_handler.get_error_statistics()
    total_errors = stats['total_errors']
    
    # Determine health status
    if total_errors == 0:
        health_status = 'healthy'
    elif stats['recovery_rate_percent'] > 80:
        health_status = 'stable'
    elif stats['recovery_rate_percent'] > 60:
        health_status = 'degraded'
    else:
        health_status = 'unstable'
    
    # Check for critical errors
    critical_errors = stats['errors_by_severity'].get('critical', 0)
    if critical_errors > 0:
        health_status = 'critical'
    
    return {
        'health_status': health_status,
        'total_errors': total_errors,
        'recovery_rate': stats['recovery_rate_percent'],
        'critical_errors': critical_errors,
        'error_statistics': stats,
        'timestamp': timezone.now().isoformat()
    }


def check_component_health(component: str) -> Dict[str, Any]:
    """
    Check health of a specific component
    
    Args:
        component: Component name to check
        
    Returns:
        Component health status
    """
    stats = error_handler.get_error_statistics()
    component_errors = stats['errors_by_component'].get(component, 0)
    
    if component_errors == 0:
        status = 'healthy'
    elif component_errors < 5:
        status = 'stable'
    elif component_errors < 20:
        status = 'degraded'
    else:
        status = 'unhealthy'
    
    return {
        'component': component,
        'status': status,
        'error_count': component_errors,
        'last_check': timezone.now().isoformat()
    }