"""
API Circuit Breaker Pattern Implementation
Provides resilient API access with automatic failure handling and recovery
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
import requests
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Circuit is open, failing fast
    HALF_OPEN = "half_open" # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5          # Failures before opening circuit
    recovery_timeout: int = 60          # Seconds before trying recovery
    timeout: int = 30                   # Request timeout in seconds
    success_threshold: int = 3          # Successes needed to close circuit from half-open
    sliding_window_size: int = 10       # Size of failure tracking window
    monitoring_period: int = 300        # Period for statistics tracking (5 minutes)


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeouts: int = 0
    circuit_opens: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    failure_history: List[datetime] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def recent_failure_rate(self) -> float:
        """Calculate recent failure rate based on sliding window"""
        if not self.failure_history:
            return 0.0
        
        now = datetime.now()
        recent_failures = [
            f for f in self.failure_history 
            if (now - f).seconds < 300  # Last 5 minutes
        ]
        
        if len(recent_failures) == 0:
            return 0.0
        
        return len(recent_failures) / max(len(self.failure_history), 1) * 100


class APICircuitBreaker:
    """
    Circuit breaker implementation for API resilience
    Automatically handles failures and provides fallback mechanisms
    """
    
    def __init__(self, 
                 name: str,
                 config: CircuitBreakerConfig = None,
                 fallback_func: Callable = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback_func = fallback_func
        
        # State management
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics tracking
        self.stats = CircuitBreakerStats()
        
        # Cache key for persistence
        self.cache_key = f"circuit_breaker:{name}"
        
        # Load persisted state
        self._load_state()
        
        logger.info(f"Initialized circuit breaker '{name}' with config: {self.config}")
    
    def _load_state(self):
        """Load circuit breaker state from cache"""
        try:
            cached_state = cache.get(self.cache_key)
            if cached_state:
                self.state = CircuitState(cached_state.get('state', CircuitState.CLOSED.value))
                self.consecutive_failures = cached_state.get('consecutive_failures', 0)
                self.last_failure_time = cached_state.get('last_failure_time')
                if isinstance(self.last_failure_time, str):
                    self.last_failure_time = datetime.fromisoformat(self.last_failure_time)
                
                logger.debug(f"Loaded circuit breaker state for '{self.name}': {self.state}")
        except Exception as e:
            logger.warning(f"Failed to load circuit breaker state: {e}")
    
    def _save_state(self):
        """Persist circuit breaker state to cache"""
        try:
            state_data = {
                'state': self.state.value,
                'consecutive_failures': self.consecutive_failures,
                'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
                'stats': {
                    'total_requests': self.stats.total_requests,
                    'successful_requests': self.stats.successful_requests,
                    'failed_requests': self.stats.failed_requests,
                    'circuit_opens': self.stats.circuit_opens
                }
            }
            
            # Cache for 1 hour
            cache.set(self.cache_key, state_data, 3600)
            
        except Exception as e:
            logger.error(f"Failed to save circuit breaker state: {e}")
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset from OPEN to HALF_OPEN"""
        if self.state != CircuitState.OPEN:
            return False
        
        if not self.last_failure_time:
            return True
        
        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.config.recovery_timeout
    
    def _record_success(self):
        """Record a successful operation"""
        with self.lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.last_success_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.consecutive_successes += 1
                self.consecutive_failures = 0
                
                # Close circuit if enough successes
                if self.consecutive_successes >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.consecutive_successes = 0
                    logger.info(f"Circuit breaker '{self.name}' closed after recovery")
            
            elif self.state == CircuitState.CLOSED:
                self.consecutive_failures = 0
            
            self._save_state()
    
    def _record_failure(self, error: Exception = None):
        """Record a failed operation"""
        with self.lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.last_failure_time = datetime.now()
            self.stats.failure_history.append(datetime.now())
            
            # Keep only recent failures
            if len(self.stats.failure_history) > self.config.sliding_window_size:
                self.stats.failure_history = self.stats.failure_history[-self.config.sliding_window_size:]
            
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_failure_time = datetime.now()
            
            # Check if we should open the circuit
            if (self.state == CircuitState.CLOSED and 
                self.consecutive_failures >= self.config.failure_threshold):
                
                self.state = CircuitState.OPEN
                self.stats.circuit_opens += 1
                logger.warning(f"Circuit breaker '{self.name}' opened after {self.consecutive_failures} failures")
            
            elif self.state == CircuitState.HALF_OPEN:
                # Failed during testing, go back to OPEN
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' failed during half-open test")
            
            if isinstance(error, requests.Timeout):
                self.stats.timeouts += 1
            
            self._save_state()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result or fallback result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open and no fallback available
        """
        with self.lock:
            # Check if we should attempt reset
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering half-open state for testing")
            
            # If circuit is open, fail fast or use fallback
            if self.state == CircuitState.OPEN:
                if self.fallback_func:
                    logger.info(f"Circuit breaker '{self.name}' is open, using fallback")
                    try:
                        return self.fallback_func(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"Fallback function failed: {e}")
                        raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open and fallback failed")
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is open")
        
        # Attempt the actual function call
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
            
        except Exception as e:
            self._record_failure(e)
            
            # Try fallback if available
            if self.fallback_func:
                logger.warning(f"Primary function failed, trying fallback for '{self.name}': {e}")
                try:
                    return self.fallback_func(*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"Both primary and fallback failed for '{self.name}': {fallback_error}")
                    raise e
            else:
                raise e
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            'name': self.name,
            'state': self.state.value,
            'success_rate': self.stats.success_rate,
            'recent_failure_rate': self.stats.recent_failure_rate,
            'total_requests': self.stats.total_requests,
            'successful_requests': self.stats.successful_requests,
            'failed_requests': self.stats.failed_requests,
            'timeouts': self.stats.timeouts,
            'circuit_opens': self.stats.circuit_opens,
            'consecutive_failures': self.consecutive_failures,
            'last_failure_time': self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
            'last_success_time': self.stats.last_success_time.isoformat() if self.stats.last_success_time else None,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'timeout': self.config.timeout
            }
        }
    
    def reset(self):
        """Manually reset circuit breaker to closed state"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.consecutive_failures = 0
            self.consecutive_successes = 0
            self.last_failure_time = None
            self._save_state()
            logger.info(f"Circuit breaker '{self.name}' manually reset")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class USDAAPICircuitBreakers:
    """
    Collection of circuit breakers for USDA APIs
    Provides resilient access to all USDA services
    """
    
    def __init__(self):
        self.breakers = {}
        self._initialize_breakers()
    
    def _initialize_breakers(self):
        """Initialize circuit breakers for different USDA APIs"""
        
        # NASS QuickStats API
        self.breakers['nass'] = APICircuitBreaker(
            name='usda_nass',
            config=CircuitBreakerConfig(
                failure_threshold=3,    # NASS is more restrictive
                recovery_timeout=120,   # 2 minutes recovery
                timeout=45,            # Longer timeout for NASS
                success_threshold=2
            ),
            fallback_func=self._nass_fallback
        )
        
        # FoodData Central API
        self.breakers['fooddata'] = APICircuitBreaker(
            name='usda_fooddata',
            config=CircuitBreakerConfig(
                failure_threshold=5,    # More tolerant
                recovery_timeout=60,    # 1 minute recovery
                timeout=30,
                success_threshold=3
            ),
            fallback_func=self._fooddata_fallback
        )
        
        # Economic Research Service API
        self.breakers['ers'] = APICircuitBreaker(
            name='usda_ers',
            config=CircuitBreakerConfig(
                failure_threshold=4,
                recovery_timeout=90,
                timeout=35,
                success_threshold=2
            ),
            fallback_func=self._ers_fallback
        )
        
        # Carbon calculation service (internal)
        self.breakers['carbon_calc'] = APICircuitBreaker(
            name='carbon_calculation',
            config=CircuitBreakerConfig(
                failure_threshold=8,    # More tolerant for internal service
                recovery_timeout=30,    # Quick recovery
                timeout=20,
                success_threshold=3
            ),
            fallback_func=self._carbon_calc_fallback
        )
        
        logger.info(f"Initialized {len(self.breakers)} USDA API circuit breakers")
    
    def _nass_fallback(self, *args, **kwargs) -> Dict[str, Any]:
        """Fallback for NASS API failures"""
        logger.info("Using NASS fallback data")
        
        # Return cached data or default structure
        from .usda_cache_service import specialized_cache
        
        if len(args) >= 2:  # crop_type, state expected
            crop_type, state = args[0], args[1]
            cached_data, _ = specialized_cache.get_cached_nass_yield(crop_type, state)
            
            if cached_data:
                cached_data['data_source'] = 'cache_fallback'
                cached_data['warning'] = 'Using cached data due to API unavailability'
                return cached_data
        
        # Last resort: return default structure
        return {
            'data': [],
            'data_source': 'fallback',
            'warning': 'NASS API unavailable, using default data'
        }
    
    def _fooddata_fallback(self, *args, **kwargs) -> Dict[str, Any]:
        """Fallback for FoodData Central API failures"""
        logger.info("Using FoodData Central fallback data")
        
        return {
            'foods': [],
            'totalHits': 0,
            'data_source': 'fallback',
            'warning': 'FoodData Central API unavailable'
        }
    
    def _ers_fallback(self, *args, **kwargs) -> Dict[str, Any]:
        """Fallback for ERS API failures"""
        logger.info("Using ERS fallback data")
        
        return {
            'data': [],
            'data_source': 'fallback',
            'warning': 'ERS API unavailable'
        }
    
    def _carbon_calc_fallback(self, crop_type: str, state: str, farm_practices: Dict) -> Dict[str, Any]:
        """Fallback for carbon calculation failures"""
        logger.info("Using carbon calculation fallback")
        
        # Provide conservative estimates based on crop type
        crop_lower = crop_type.lower()
        
        # Conservative emission estimates by crop type
        emission_estimates = {
            'corn': {'co2e': 0.8, 'efficiency_score': 65},
            'soybeans': {'co2e': 0.4, 'efficiency_score': 80},
            'wheat': {'co2e': 0.6, 'efficiency_score': 70},
            'citrus': {'co2e': 1.2, 'efficiency_score': 60},
            'default': {'co2e': 0.7, 'efficiency_score': 65}
        }
        
        estimate = emission_estimates.get(crop_lower, emission_estimates['default'])
        
        return {
            'carbon_intensity': estimate['co2e'],
            'total_emissions': estimate['co2e'] * farm_practices.get('area_hectares', 1),
            'efficiency_score': estimate['efficiency_score'],
            'data_source': 'fallback_estimate',
            'confidence_level': 'low',
            'warning': 'Using conservative estimates due to calculation service unavailability',
            'calculation_method': 'fallback_conservative'
        }
    
    def get_breaker(self, api_name: str) -> APICircuitBreaker:
        """Get specific circuit breaker"""
        if api_name not in self.breakers:
            raise ValueError(f"Unknown API circuit breaker: {api_name}")
        return self.breakers[api_name]
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all circuit breakers"""
        return {
            name: breaker.get_stats() 
            for name, breaker in self.breakers.items()
        }
    
    def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            breaker.reset()
        logger.info("Reset all USDA API circuit breakers")
    
    def health_check(self) -> Dict[str, Any]:
        """Get overall health status of all APIs"""
        stats = self.get_all_stats()
        
        health_status = {
            'overall_status': 'healthy',
            'unhealthy_apis': [],
            'degraded_apis': [],
            'healthy_apis': [],
            'total_requests': 0,
            'total_success_rate': 0
        }
        
        total_requests = 0
        total_successes = 0
        
        for api_name, api_stats in stats.items():
            total_requests += api_stats['total_requests']
            total_successes += api_stats['successful_requests']
            
            # Determine health status
            if api_stats['state'] == 'open':
                health_status['unhealthy_apis'].append(api_name)
                health_status['overall_status'] = 'degraded'
            elif api_stats['success_rate'] < 80:
                health_status['degraded_apis'].append(api_name)
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'degraded'
            else:
                health_status['healthy_apis'].append(api_name)
        
        # Calculate overall success rate
        if total_requests > 0:
            health_status['total_success_rate'] = (total_successes / total_requests) * 100
        else:
            health_status['total_success_rate'] = 100
        
        health_status['total_requests'] = total_requests
        
        return health_status


# Global circuit breaker manager
usda_circuit_breakers = USDAAPICircuitBreakers()


def with_circuit_breaker(api_name: str):
    """
    Decorator to wrap functions with circuit breaker protection
    
    Usage:
        @with_circuit_breaker('nass')
        def fetch_nass_data(crop, state):
            # API call here
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            breaker = usda_circuit_breakers.get_breaker(api_name)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


# Utility functions for easy integration
def safe_api_call(api_name: str, func: Callable, *args, **kwargs) -> Any:
    """
    Safely execute an API call with circuit breaker protection
    
    Args:
        api_name: Name of the API circuit breaker to use
        func: Function to execute
        *args, **kwargs: Arguments for the function
        
    Returns:
        Function result or fallback result
    """
    breaker = usda_circuit_breakers.get_breaker(api_name)
    return breaker.call(func, *args, **kwargs)


def get_api_health_status() -> Dict[str, Any]:
    """Get current health status of all USDA APIs"""
    return usda_circuit_breakers.health_check()


def reset_api_circuit_breakers():
    """Reset all USDA API circuit breakers"""
    usda_circuit_breakers.reset_all()