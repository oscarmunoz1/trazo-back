"""
USDA API Comprehensive Caching Service
Implements intelligent caching for all USDA APIs with performance optimization
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
import redis
from dataclasses import dataclass, asdict
from enum import Enum
import pickle
import zlib

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """Cache strategies for different data types"""
    STATIC_DATA = "static"          # Long-term cache (24 hours+)
    DYNAMIC_DATA = "dynamic"        # Medium-term cache (2-6 hours)
    REALTIME_DATA = "realtime"      # Short-term cache (15-30 minutes)
    COMPUTATION = "computation"      # Cached calculations (1-4 hours)


@dataclass
class CacheConfig:
    """Configuration for cache behavior"""
    ttl: int                        # Time to live in seconds
    compress: bool = True           # Whether to compress data
    version_key: bool = True        # Whether to include version in key
    fallback_ttl: int = 300        # Fallback TTL on errors
    max_retries: int = 3           # Max retries for cache operations
    

class USDADataCacheManager:
    """
    Comprehensive caching manager for USDA API data
    Handles intelligent caching strategies based on data type and usage patterns
    """
    
    def __init__(self):
        self.redis_client = self._get_redis_client()
        self.cache_prefix = "usda_api"
        self.version = "v2.1"
        
        # Cache strategies configuration
        self.cache_strategies = {
            CacheStrategy.STATIC_DATA: CacheConfig(
                ttl=86400,         # 24 hours - for crop metadata, emission factors
                compress=True,
                version_key=True
            ),
            CacheStrategy.DYNAMIC_DATA: CacheConfig(
                ttl=7200,          # 2 hours - for yield data, weather data
                compress=True,
                version_key=True
            ),
            CacheStrategy.REALTIME_DATA: CacheConfig(
                ttl=1800,          # 30 minutes - for market prices, current conditions
                compress=False,    # Faster access for frequent queries
                version_key=False
            ),
            CacheStrategy.COMPUTATION: CacheConfig(
                ttl=14400,         # 4 hours - for carbon calculations, benchmarks
                compress=True,
                version_key=True
            )
        }
        
        # Performance tracking
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'total_requests': 0
        }
    
    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with connection pooling"""
        try:
            # Use Django's Redis cache backend
            if hasattr(cache, '_cache') and hasattr(cache._cache, '_serializer'):
                # Get Redis connection from Django cache
                return cache._cache.get_client(write=True)
            return None
        except Exception as e:
            logger.warning(f"Could not establish Redis connection: {e}")
            return None
    
    def _generate_cache_key(self, 
                           data_type: str, 
                           identifier: str, 
                           strategy: CacheStrategy,
                           params: Dict = None) -> str:
        """Generate intelligent cache key with versioning and params"""
        
        # Create base key components
        key_parts = [self.cache_prefix, data_type, identifier]
        
        # Add version if strategy requires it
        config = self.cache_strategies[strategy]
        if config.version_key:
            key_parts.append(self.version)
        
        # Add parameter hash for complex queries
        if params:
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key_parts.append(param_hash)
        
        return ":".join(key_parts)
    
    def _compress_data(self, data: Any) -> bytes:
        """Compress data using zlib for storage efficiency"""
        try:
            serialized = pickle.dumps(data)
            compressed = zlib.compress(serialized, level=6)  # Balanced compression
            return compressed
        except Exception as e:
            logger.error(f"Failed to compress data: {e}")
            return pickle.dumps(data)  # Fallback to uncompressed
    
    def _decompress_data(self, compressed_data: bytes) -> Any:
        """Decompress data from cache"""
        try:
            # Try to decompress first
            try:
                decompressed = zlib.decompress(compressed_data)
                return pickle.loads(decompressed)
            except zlib.error:
                # Data might not be compressed (backward compatibility)
                return pickle.loads(compressed_data)
        except Exception as e:
            logger.error(f"Failed to decompress data: {e}")
            return None
    
    def set_cached_data(self, 
                       data_type: str,
                       identifier: str, 
                       data: Any,
                       strategy: CacheStrategy = CacheStrategy.DYNAMIC_DATA,
                       params: Dict = None,
                       custom_ttl: int = None) -> bool:
        """
        Store data in cache with intelligent compression and versioning
        
        Args:
            data_type: Type of data (e.g., 'nass_yield', 'carbon_calculation')
            identifier: Unique identifier (e.g., 'corn_iowa_2023')
            data: Data to cache
            strategy: Caching strategy to use
            params: Additional parameters for key generation
            custom_ttl: Override default TTL
        
        Returns:
            bool: Success status
        """
        try:
            self.cache_stats['total_requests'] += 1
            
            config = self.cache_strategies[strategy]
            cache_key = self._generate_cache_key(data_type, identifier, strategy, params)
            
            # Prepare data for storage
            cache_data = {
                'data': data,
                'timestamp': timezone.now().isoformat(),
                'strategy': strategy.value,
                'version': self.version
            }
            
            # Apply compression if configured
            if config.compress:
                processed_data = self._compress_data(cache_data)
            else:
                processed_data = pickle.dumps(cache_data)
            
            # Set TTL
            ttl = custom_ttl or config.ttl
            
            # Store in cache with retry logic
            for attempt in range(config.max_retries):
                try:
                    if self.redis_client:
                        # Use Redis directly for better control
                        self.redis_client.setex(cache_key, ttl, processed_data)
                    else:
                        # Fallback to Django cache
                        cache.set(cache_key, processed_data, ttl)
                    
                    logger.debug(f"Cached {data_type} data: {cache_key} (TTL: {ttl}s)")
                    return True
                    
                except Exception as e:
                    if attempt == config.max_retries - 1:
                        logger.error(f"Failed to cache data after {config.max_retries} attempts: {e}")
                        self.cache_stats['errors'] += 1
                        return False
                    continue
                    
        except Exception as e:
            logger.error(f"Error in set_cached_data: {e}")
            self.cache_stats['errors'] += 1
            return False
    
    def get_cached_data(self, 
                       data_type: str,
                       identifier: str, 
                       strategy: CacheStrategy = CacheStrategy.DYNAMIC_DATA,
                       params: Dict = None) -> Tuple[Any, bool]:
        """
        Retrieve data from cache with automatic decompression
        
        Returns:
            Tuple[data, is_fresh]: Data and freshness indicator
        """
        try:
            self.cache_stats['total_requests'] += 1
            
            cache_key = self._generate_cache_key(data_type, identifier, strategy, params)
            
            # Try to get from cache
            cached_data = None
            if self.redis_client:
                try:
                    cached_data = self.redis_client.get(cache_key)
                except Exception:
                    pass
            
            if not cached_data:
                # Fallback to Django cache
                cached_data = cache.get(cache_key)
            
            if cached_data is None:
                self.cache_stats['misses'] += 1
                return None, False
            
            # Decompress and validate data
            if isinstance(cached_data, bytes):
                cache_data = self._decompress_data(cached_data)
            else:
                cache_data = cached_data  # Backward compatibility
            
            if not cache_data or not isinstance(cache_data, dict):
                logger.warning(f"Invalid cached data format for key: {cache_key}")
                self.cache_stats['errors'] += 1
                return None, False
            
            # Check data freshness
            config = self.cache_strategies[strategy]
            timestamp = datetime.fromisoformat(cache_data['timestamp'].replace('Z', '+00:00'))
            age = (timezone.now() - timestamp).total_seconds()
            is_fresh = age < (config.ttl * 0.8)  # Consider fresh if less than 80% of TTL
            
            self.cache_stats['hits'] += 1
            logger.debug(f"Cache hit for {data_type}: {cache_key} (age: {age:.0f}s)")
            
            return cache_data['data'], is_fresh
            
        except Exception as e:
            logger.error(f"Error retrieving cached data: {e}")
            self.cache_stats['errors'] += 1
            return None, False
    
    def invalidate_cache(self, 
                        data_type: str,
                        identifier: str = None,
                        strategy: CacheStrategy = None) -> int:
        """
        Invalidate cache entries with pattern matching
        
        Returns:
            int: Number of keys invalidated
        """
        try:
            if identifier and strategy:
                # Invalidate specific key
                cache_key = self._generate_cache_key(data_type, identifier, strategy)
                if self.redis_client:
                    result = self.redis_client.delete(cache_key)
                else:
                    cache.delete(cache_key)
                    result = 1
                
                logger.info(f"Invalidated cache key: {cache_key}")
                return result
            else:
                # Pattern-based invalidation
                pattern = f"{self.cache_prefix}:{data_type}:*"
                invalidated = 0
                
                if self.redis_client:
                    try:
                        keys = self.redis_client.keys(pattern)
                        if keys:
                            invalidated = self.redis_client.delete(*keys)
                    except Exception as e:
                        logger.error(f"Redis pattern delete failed: {e}")
                
                logger.info(f"Invalidated {invalidated} cache entries for pattern: {pattern}")
                return invalidated
                
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.cache_stats['total_requests']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests,
            'cache_hits': self.cache_stats['hits'],
            'cache_misses': self.cache_stats['misses'],
            'errors': self.cache_stats['errors'],
            'cache_size_estimate': self._estimate_cache_size()
        }
    
    def _estimate_cache_size(self) -> str:
        """Estimate cache size (Redis only)"""
        try:
            if self.redis_client:
                info = self.redis_client.info('memory')
                used_memory = info.get('used_memory_human', 'Unknown')
                return used_memory
            return "N/A (Django cache)"
        except Exception:
            return "Unknown"
    
    def preload_common_data(self) -> Dict[str, bool]:
        """
        Preload commonly accessed data to improve performance
        Should be called during application startup or scheduled
        """
        preload_results = {}
        
        try:
            # Common crop types and states
            common_crops = ['corn', 'soybeans', 'wheat', 'citrus']
            common_states = ['IA', 'IL', 'CA', 'TX', 'FL']
            
            from .real_usda_integration import RealUSDAAPIClient
            usda_client = RealUSDAAPIClient()
            
            for crop in common_crops:
                for state in common_states:
                    try:
                        # Preload NASS yield data
                        data_key = f"{crop}_{state}_yield"
                        
                        # Check if already cached
                        cached_data, _ = self.get_cached_data(
                            'nass_yield', 
                            data_key, 
                            CacheStrategy.STATIC_DATA
                        )
                        
                        if not cached_data:
                            # Fetch and cache
                            yield_data = usda_client.get_nass_crop_data(crop, state)
                            if yield_data:
                                success = self.set_cached_data(
                                    'nass_yield',
                                    data_key,
                                    yield_data,
                                    CacheStrategy.STATIC_DATA
                                )
                                preload_results[data_key] = success
                            else:
                                preload_results[data_key] = False
                        else:
                            preload_results[data_key] = True  # Already cached
                            
                    except Exception as e:
                        logger.error(f"Failed to preload {crop} {state}: {e}")
                        preload_results[f"{crop}_{state}_yield"] = False
            
            successful_preloads = sum(1 for success in preload_results.values() if success)
            total_preloads = len(preload_results)
            
            logger.info(f"Preloaded {successful_preloads}/{total_preloads} common USDA datasets")
            
        except Exception as e:
            logger.error(f"Error during data preloading: {e}")
        
        return preload_results
    
    def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries
        Returns number of entries cleaned
        """
        try:
            if not self.redis_client:
                logger.warning("Redis not available for cleanup")
                return 0
            
            pattern = f"{self.cache_prefix}:*"
            keys = self.redis_client.keys(pattern)
            
            expired_count = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -2:  # Key doesn't exist
                    expired_count += 1
                elif ttl == -1:  # Key exists but no TTL set
                    # Set a default TTL for keys without expiration
                    self.redis_client.expire(key, 86400)  # 24 hours default
            
            logger.info(f"Cleaned up {expired_count} expired cache entries")
            return expired_count
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            return 0


# Specialized caching functions for different USDA data types

class USDASpecializedCache:
    """Specialized caching functions for specific USDA data types"""
    
    def __init__(self):
        self.cache_manager = USDADataCacheManager()
    
    def cache_nass_yield_data(self, crop: str, state: str, data: Dict) -> bool:
        """Cache NASS yield data with appropriate strategy"""
        identifier = f"{crop.lower()}_{state.upper()}_yield"
        return self.cache_manager.set_cached_data(
            'nass_yield',
            identifier,
            data,
            CacheStrategy.STATIC_DATA  # Yield data changes infrequently
        )
    
    def get_cached_nass_yield(self, crop: str, state: str) -> Tuple[Dict, bool]:
        """Get cached NASS yield data"""
        identifier = f"{crop.lower()}_{state.upper()}_yield"
        return self.cache_manager.get_cached_data(
            'nass_yield',
            identifier,
            CacheStrategy.STATIC_DATA
        )
    
    def cache_carbon_calculation(self, 
                               crop: str, 
                               state: str, 
                               inputs_hash: str,
                               calculation: Dict) -> bool:
        """Cache carbon calculation results"""
        identifier = f"{crop.lower()}_{state.upper()}_{inputs_hash}"
        return self.cache_manager.set_cached_data(
            'carbon_calculation',
            identifier,
            calculation,
            CacheStrategy.COMPUTATION
        )
    
    def get_cached_carbon_calculation(self, 
                                    crop: str, 
                                    state: str, 
                                    inputs_hash: str) -> Tuple[Dict, bool]:
        """Get cached carbon calculation"""
        identifier = f"{crop.lower()}_{state.upper()}_{inputs_hash}"
        return self.cache_manager.get_cached_data(
            'carbon_calculation',
            identifier,
            CacheStrategy.COMPUTATION
        )
    
    def cache_benchmark_data(self, crop: str, state: str, benchmark: float) -> bool:
        """Cache benchmark yield data"""
        identifier = f"{crop.lower()}_{state.upper()}_benchmark"
        return self.cache_manager.set_cached_data(
            'benchmark_yield',
            identifier,
            {'benchmark_yield': benchmark, 'crop': crop, 'state': state},
            CacheStrategy.STATIC_DATA
        )
    
    def get_cached_benchmark(self, crop: str, state: str) -> Tuple[float, bool]:
        """Get cached benchmark yield"""
        identifier = f"{crop.lower()}_{state.upper()}_benchmark"
        data, is_fresh = self.cache_manager.get_cached_data(
            'benchmark_yield',
            identifier,
            CacheStrategy.STATIC_DATA
        )
        
        if data and 'benchmark_yield' in data:
            return data['benchmark_yield'], is_fresh
        return None, False


# Global cache manager instance
usda_cache = USDADataCacheManager()
specialized_cache = USDASpecializedCache()

# Utility functions for easy integration
def cache_usda_data(data_type: str, identifier: str, data: Any, 
                   strategy: CacheStrategy = CacheStrategy.DYNAMIC_DATA) -> bool:
    """Convenience function to cache USDA data"""
    return usda_cache.set_cached_data(data_type, identifier, data, strategy)

def get_usda_cached_data(data_type: str, identifier: str, 
                        strategy: CacheStrategy = CacheStrategy.DYNAMIC_DATA) -> Tuple[Any, bool]:
    """Convenience function to get cached USDA data"""
    return usda_cache.get_cached_data(data_type, identifier, strategy)

def clear_usda_cache(data_type: str = None) -> int:
    """Convenience function to clear USDA cache"""
    if data_type:
        return usda_cache.invalidate_cache(data_type)
    else:
        # Clear all USDA cache
        pattern_count = 0
        for dt in ['nass_yield', 'carbon_calculation', 'benchmark_yield', 'fooddata']:
            pattern_count += usda_cache.invalidate_cache(dt)
        return pattern_count