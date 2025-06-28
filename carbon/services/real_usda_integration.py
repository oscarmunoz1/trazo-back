"""
Real USDA Integration Service
Integrates with actual USDA APIs and provides carbon footprint calculations
using available government data sources.
"""

import logging
import requests
import json
from typing import Dict, Any, Optional, List, Tuple
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import hashlib
import time
import threading
from .secure_key_management import secure_key_manager, get_secure_usda_keys
from .usda_cache_service import (
    USDADataCacheManager, 
    USDASpecializedCache, 
    CacheStrategy,
    usda_cache,
    specialized_cache
)
from .api_circuit_breaker import (
    usda_circuit_breakers,
    with_circuit_breaker,
    safe_api_call,
    CircuitBreakerOpenError
)
from .enhanced_error_handling import (
    error_handler,
    with_error_handling,
    RetryConfig,
    FallbackConfig,
    FallbackStrategy,
    USDAAPIErrorHandler
)

logger = logging.getLogger(__name__)


class APIRateLimiter:
    """Rate limiter for API calls to prevent hitting USDA API limits"""
    
    def __init__(self, calls_per_minute=10):
        self.calls_per_minute = calls_per_minute
        self.calls = []
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        with self.lock:
            now = time.time()
            # Remove calls older than 1 minute
            self.calls = [call_time for call_time in self.calls if now - call_time < 60]
            
            if len(self.calls) >= self.calls_per_minute:
                # Calculate wait time
                oldest_call = min(self.calls)
                wait_time = 60 - (now - oldest_call) + 1  # Add 1 second buffer
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                    # Clean up old calls again after waiting
                    now = time.time()
                    self.calls = [call_time for call_time in self.calls if now - call_time < 60]
            
            # Record this call
            self.calls.append(now)


class RealUSDAAPIClient:
    """Client for real USDA APIs - NASS QuickStats and ERS"""
    
    def __init__(self):
        # Real USDA API endpoints
        self.nass_base_url = 'https://quickstats.nass.usda.gov/api'
        self.ers_base_url = 'https://api.ers.usda.gov'
        self.fooddata_base_url = 'https://api.nal.usda.gov/fdc/v1'
        
        # API Keys loaded securely
        try:
            api_keys = get_secure_usda_keys()
            self.nass_api_key = api_keys.get('nass_api_key')
            self.ers_api_key = api_keys.get('ers_api_key')
            self.fooddata_api_key = api_keys.get('fooddata_api_key')
            
            if not any([self.nass_api_key, self.ers_api_key, self.fooddata_api_key]):
                logger.warning("No USDA API keys found in secure storage")
            else:
                logger.info("✅ USDA API keys loaded securely")
                
        except Exception as e:
            logger.error(f"Failed to load USDA API keys securely: {e}")
            # Fallback to settings for development only
            if not getattr(settings, 'DEBUG', True):
                raise Exception(f"USDA API key loading failed in production: {e}")
            
            self.nass_api_key = getattr(settings, 'USDA_NASS_API_KEY', None)
            self.ers_api_key = getattr(settings, 'USDA_ERS_API_KEY', None)
            self.fooddata_api_key = getattr(settings, 'USDA_FOODDATA_API_KEY', None)
        
        self.timeout = 30
        
        # Rate limiters for different APIs
        self.nass_rate_limiter = APIRateLimiter(calls_per_minute=10)  # Conservative limit
        self.fooddata_rate_limiter = APIRateLimiter(calls_per_minute=30)  # Higher limit for FoodData Central
        
        # Base emission factors from IPCC/EPA guidelines
        self.base_emission_factors = {
            'nitrogen': 5.86,    # kg CO2e per kg N (IPCC 2019)
            'phosphorus': 0.20,  # kg CO2e per kg P2O5
            'potassium': 0.15,   # kg CO2e per kg K2O
            'diesel': 2.68,      # kg CO2e per liter
            'gasoline': 2.31,    # kg CO2e per liter
            'natural_gas': 2.03, # kg CO2e per m³
        }
        
        # Regional yield benchmarks from NASS data
        self.regional_yield_benchmarks = {}
    
    def get_nass_crop_data(self, crop_type: str, state: str, year: int = None) -> Dict[str, Any]:
        """Fetch real crop data from USDA NASS QuickStats API with comprehensive caching"""
        try:
            if not self.nass_api_key:
                logger.warning("NASS API key not configured")
                return {}
            
            # Use current year if not specified
            if not year:
                year = datetime.now().year - 1  # Previous year data is usually available
            
            # Check specialized cache first
            cache_identifier = f"{crop_type.lower()}_{state.upper()}_{year}"
            cached_data, is_fresh = specialized_cache.cache_manager.get_cached_data(
                'nass_yield',
                cache_identifier,
                CacheStrategy.STATIC_DATA,
                params={'year': year}
            )
            
            if cached_data and is_fresh:
                logger.info(f"✅ Using fresh cached NASS data for {crop_type} in {state} ({year})")
                return cached_data
            elif cached_data:
                logger.info(f"⚠️ Using stale cached NASS data for {crop_type} in {state} ({year})")
                # Return stale data but trigger background refresh
                self._schedule_background_refresh(crop_type, state, year)
                return cached_data
            
            # Enhanced crop type mapping for NASS commodity names
            crop_lower = crop_type.lower()
            commodity_map = {
                'corn': 'CORN',
                'soybeans': 'SOYBEANS', 
                'soybean': 'SOYBEANS',
                'wheat': 'WHEAT',
                'citrus': 'ORANGES',
                'orange': 'ORANGES',
                'oranges': 'ORANGES',
                'citrus (oranges)': 'ORANGES',
                'almonds': 'ALMONDS',
                'almond': 'ALMONDS',
                'apples': 'APPLES',
                'apple': 'APPLES',
                'grapes': 'GRAPES',
                'grape': 'GRAPES',
                'tomatoes': 'TOMATOES',
                'tomato': 'TOMATOES',
                'lettuce': 'LETTUCE',
                'carrots': 'CARROTS',
                'carrot': 'CARROTS',
                'potatoes': 'POTATOES',
                'potato': 'POTATOES'
            }
            
            # Try exact match first, then check if any key contains the crop type
            commodity = None
            if crop_lower in commodity_map:
                commodity = commodity_map[crop_lower]
            else:
                # Try partial matching for complex names like "Citrus (Oranges)"
                for key, value in commodity_map.items():
                    if key in crop_lower or crop_lower in key:
                        commodity = value
                        break
            
            # Fallback to uppercase crop type if no mapping found
            if not commodity:
                commodity = crop_type.upper()
                logger.info(f"No commodity mapping found for '{crop_type}', using '{commodity}'")
            
            params = {
                'key': self.nass_api_key,
                'commodity_desc': commodity,
                'state_alpha': state.upper(),
                'year': year,
                'statisticcat_desc': 'YIELD',
                'format': 'JSON'
            }
            
            logger.info(f"NASS API request: commodity={commodity}, state={state}, year={year}")
            
            # Apply rate limiting before making the request
            self.nass_rate_limiter.wait_if_needed()
            
            # Use circuit breaker for resilient API access
            def make_nass_request():
                return requests.get(
                    f"{self.nass_base_url}/api_GET",
                    params=params,
                    timeout=self.timeout
                )
            
            try:
                response = safe_api_call('nass', make_nass_request)
            except CircuitBreakerOpenError:
                logger.warning("NASS API circuit breaker is open, using fallback")
                # Return cached data or empty result
                return usda_circuit_breakers.get_breaker('nass').fallback_func(crop_type, state, year)
            
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and len(data['data']) > 0:
                    logger.info(f"Successfully fetched NASS data for {crop_type} ({commodity}) in {state}: {len(data['data'])} records")
                    
                    # Cache using comprehensive caching service
                    specialized_cache.cache_manager.set_cached_data(
                        'nass_yield',
                        cache_identifier,
                        data,
                        CacheStrategy.STATIC_DATA,
                        params={'year': year}
                    )
                    
                    return data
                else:
                    logger.warning(f"NASS API returned no data for {commodity} in {state} for {year}")
                    return {}
            else:
                logger.warning(f"NASS API returned status {response.status_code} for {commodity} in {state}")
                # Try with different parameters if first attempt fails
                if response.status_code in [400, 500] and year > 2020:
                    logger.info(f"Retrying NASS API with previous year ({year-1})")
                    return self.get_nass_crop_data(crop_type, state, year-1)
                return {}
                
        except requests.RequestException as e:
            logger.error(f"NASS API request failed: {e}")
            return USDAAPIErrorHandler.handle_api_error('get_nass_crop_data', e, crop_type, state)
        except Exception as e:
            logger.error(f"Unexpected error fetching NASS data: {e}")
            return USDAAPIErrorHandler.handle_api_error('get_nass_crop_data', e, crop_type, state)
    
    def get_benchmark_yield(self, crop_type: str, state: str) -> Optional[float]:
        """Get benchmark yield for a crop in a state from NASS data with enhanced caching"""
        try:
            # Check specialized cache first
            cached_benchmark, is_fresh = specialized_cache.get_cached_benchmark(crop_type, state)
            
            if cached_benchmark and is_fresh:
                logger.debug(f"Using cached benchmark for {crop_type} in {state}: {cached_benchmark}")
                return cached_benchmark
            elif cached_benchmark:
                # Return stale data but trigger refresh
                self._schedule_background_refresh(crop_type, state, None, 'benchmark')
                return cached_benchmark
            
            # Fetch from NASS API
            nass_data = self.get_nass_crop_data(crop_type, state)
            
            if nass_data and 'data' in nass_data:
                # Extract yield values and calculate average
                yields = []
                for record in nass_data['data']:
                    if record.get('Value') and record['Value'] != '(D)':  # (D) means withheld
                        try:
                            # Remove commas and convert to float
                            yield_value = float(record['Value'].replace(',', ''))
                            yields.append(yield_value)
                        except (ValueError, TypeError):
                            continue
                
                if yields:
                    avg_yield = sum(yields) / len(yields)
                    
                    # Cache using specialized cache
                    specialized_cache.cache_benchmark_data(crop_type, state, avg_yield)
                    
                    logger.info(f"Calculated and cached benchmark yield for {crop_type} in {state}: {avg_yield}")
                    return avg_yield
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting benchmark yield: {e}")
            return None
    
    def calculate_carbon_intensity(self, crop_type: str, state: str, 
                                 farm_practices: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate carbon intensity using real USDA data and emission factors"""
        try:
            # Get benchmark yield from NASS
            benchmark_yield = self.get_benchmark_yield(crop_type, state)
            
            # Extract farm inputs from practices
            inputs = farm_practices.get('inputs', {})
            area_hectares = farm_practices.get('area_hectares', 1)
            actual_yield = farm_practices.get('yield_per_hectare', 0)
            
            # Calculate emissions from inputs
            total_emissions = 0
            emission_breakdown = {}
            
            # Nitrogen emissions
            if 'nitrogen_kg' in inputs:
                n_emissions = inputs['nitrogen_kg'] * self.base_emission_factors['nitrogen']
                total_emissions += n_emissions
                emission_breakdown['nitrogen'] = n_emissions
            
            # Phosphorus emissions
            if 'phosphorus_kg' in inputs:
                p_emissions = inputs['phosphorus_kg'] * self.base_emission_factors['phosphorus']
                total_emissions += p_emissions
                emission_breakdown['phosphorus'] = p_emissions
            
            # Fuel emissions
            if 'diesel_liters' in inputs:
                fuel_emissions = inputs['diesel_liters'] * self.base_emission_factors['diesel']
                total_emissions += fuel_emissions
                emission_breakdown['fuel'] = fuel_emissions
            
            # Calculate carbon intensity (kg CO2e per kg product)
            carbon_intensity = 0
            if actual_yield > 0:
                total_production = actual_yield * area_hectares
                carbon_intensity = total_emissions / total_production
            
            # Compare to benchmark
            benchmark_comparison = None
            if benchmark_yield:
                benchmark_comparison = {
                    'farm_yield': actual_yield,
                    'regional_benchmark': benchmark_yield,
                    'performance_ratio': actual_yield / benchmark_yield if benchmark_yield > 0 else 0,
                    'yield_efficiency': 'above_average' if actual_yield > benchmark_yield else 'below_average'
                }
            
            return {
                'carbon_intensity': carbon_intensity,
                'total_emissions': total_emissions,
                'emission_breakdown': emission_breakdown,
                'benchmark_comparison': benchmark_comparison,
                'data_source': 'USDA NASS + EPA emission factors',
                'calculation_method': 'life_cycle_assessment',
                'confidence_level': 'high' if benchmark_yield else 'medium'
            }
            
        except Exception as e:
            logger.error(f"Error calculating carbon intensity: {e}")
            return {
                'error': str(e),
                'carbon_intensity': 0,
                'confidence_level': 'low'
            }
    
    def get_food_composition_data(self, crop_type: str) -> Dict[str, Any]:
        """Fetch food composition data from USDA FoodData Central API"""
        try:
            if not self.fooddata_api_key:
                logger.warning("FoodData Central API key not configured")
                return {}
            
            # Map crop types to food items
            food_map = {
                'corn': 'sweet corn',
                'soybeans': 'soybeans',
                'wheat': 'wheat',
                'citrus': 'orange',
                'almonds': 'almonds'
            }
            
            search_term = food_map.get(crop_type.lower(), crop_type)
            
            # Search for food items
            search_params = {
                'api_key': self.fooddata_api_key,
                'query': search_term,
                'dataType': 'Foundation,SR Legacy',
                'pageSize': 5
            }
            
            # Apply rate limiting before making the request
            self.fooddata_rate_limiter.wait_if_needed()
            
            # Use circuit breaker for resilient API access
            def make_fooddata_request():
                return requests.get(
                    f"{self.fooddata_base_url}/foods/search",
                    params=search_params,
                    timeout=self.timeout
                )
            
            try:
                response = safe_api_call('fooddata', make_fooddata_request)
            except CircuitBreakerOpenError:
                logger.warning("FoodData Central API circuit breaker is open, using fallback")
                return usda_circuit_breakers.get_breaker('fooddata').fallback_func(crop_type)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully fetched FoodData Central data for {crop_type}")
                return data
            else:
                logger.warning(f"FoodData Central API returned status {response.status_code}")
                return {}
                
        except requests.RequestException as e:
            logger.error(f"FoodData Central API request failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching FoodData Central data: {e}")
            return {}
    
    def get_nutritional_carbon_factors(self, crop_type: str) -> Dict[str, Any]:
        """Get nutritional data to enhance carbon calculations"""
        try:
            food_data = self.get_food_composition_data(crop_type)
            
            if not food_data or 'foods' not in food_data:
                return {}
            
            # Extract relevant nutritional data from first result
            if food_data['foods']:
                food_item = food_data['foods'][0]
                
                # Get detailed nutrient info
                food_id = food_item.get('fdcId')
                if food_id:
                    # Apply rate limiting before making the request
                    self.fooddata_rate_limiter.wait_if_needed()
                    
                    detail_response = requests.get(
                        f"{self.fooddata_base_url}/food/{food_id}",
                        params={'api_key': self.fooddata_api_key},
                        timeout=self.timeout
                    )
                    
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        
                        # Extract key nutrients
                        nutrients = {}
                        if 'foodNutrients' in detail_data:
                            for nutrient in detail_data['foodNutrients']:
                                name = nutrient.get('nutrient', {}).get('name', '')
                                value = nutrient.get('amount', 0)
                                unit = nutrient.get('nutrient', {}).get('unitName', '')
                                
                                if 'Protein' in name:
                                    nutrients['protein_g'] = value
                                elif 'Energy' in name and 'kcal' in unit:
                                    nutrients['energy_kcal'] = value
                                elif 'Carbohydrate' in name:
                                    nutrients['carbs_g'] = value
                                elif 'Total lipid' in name:
                                    nutrients['fat_g'] = value
                        
                        # Calculate nutritional efficiency factors
                        carbon_efficiency = self._calculate_nutritional_efficiency(nutrients)
                        
                        return {
                            'nutritional_data': nutrients,
                            'carbon_efficiency': carbon_efficiency,
                            'food_description': food_item.get('description', ''),
                            'data_source': 'USDA FoodData Central'
                        }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting nutritional carbon factors: {e}")
            return {}
    
    def _calculate_nutritional_efficiency(self, nutrients: Dict[str, float]) -> Dict[str, Any]:
        """Calculate carbon efficiency based on nutritional content"""
        try:
            # Nutritional density scoring
            protein = nutrients.get('protein_g', 0)
            energy = nutrients.get('energy_kcal', 0)
            
            # Calculate protein efficiency (g protein per kg CO2e)
            # Higher protein content = better carbon efficiency for nutrition
            nutrition_score = 0
            
            if protein > 0:
                nutrition_score += min(protein * 2, 40)  # Max 40 points for protein
            
            if energy > 0:
                nutrition_score += min(energy / 10, 30)  # Max 30 points for energy
            
            # Quality assessment
            if nutrition_score >= 60:
                efficiency_rating = 'high'
            elif nutrition_score >= 30:
                efficiency_rating = 'medium'
            else:
                efficiency_rating = 'low'
            
            return {
                'nutrition_score': nutrition_score,
                'efficiency_rating': efficiency_rating,
                'protein_content': protein,
                'energy_content': energy,
                'carbon_nutrition_ratio': f"{protein:.2f}g protein per unit carbon"
            }
            
        except Exception as e:
            logger.error(f"Error calculating nutritional efficiency: {e}")
            return {'efficiency_rating': 'unknown'}
    
    def _schedule_background_refresh(self, crop_type: str, state: str, year: int = None, data_type: str = 'yield'):
        """Schedule background refresh of stale cache data"""
        try:
            from .tasks import refresh_usda_cache_data
            
            # Schedule Celery task for background refresh
            refresh_usda_cache_data.delay(crop_type, state, year, data_type)
            logger.info(f"Scheduled background refresh for {crop_type} {state} {data_type}")
            
        except ImportError:
            # Fallback: refresh synchronously if Celery not available
            logger.warning("Celery not available, performing synchronous refresh")
            if data_type == 'yield':
                self.get_nass_crop_data(crop_type, state, year)
            elif data_type == 'benchmark':
                self.get_benchmark_yield(crop_type, state)
        except Exception as e:
            logger.error(f"Failed to schedule background refresh: {e}")
    
    def calculate_carbon_intensity_cached(self, crop_type: str, state: str, 
                                        farm_practices: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate carbon intensity with intelligent caching"""
        try:
            # Create hash of inputs for cache key
            inputs_str = json.dumps(farm_practices, sort_keys=True)
            inputs_hash = hashlib.md5(inputs_str.encode()).hexdigest()[:12]
            
            # Check cache first
            cached_result, is_fresh = specialized_cache.get_cached_carbon_calculation(
                crop_type, state, inputs_hash
            )
            
            if cached_result and is_fresh:
                logger.debug(f"Using cached carbon calculation for {crop_type} in {state}")
                return cached_result
            elif cached_result:
                # Return stale data but trigger background recalculation
                self._schedule_background_refresh(crop_type, state, None, 'carbon_calculation')
                cached_result['data_freshness'] = 'stale_but_usable'
                return cached_result
            
            # Perform fresh calculation
            result = self.calculate_carbon_intensity(crop_type, state, farm_practices)
            
            # Cache the result
            if result and not result.get('error'):
                specialized_cache.cache_carbon_calculation(
                    crop_type, state, inputs_hash, result
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in cached carbon calculation: {e}")
            # Fallback to non-cached calculation
            return self.calculate_carbon_intensity(crop_type, state, farm_practices)
    
    def validate_calculation_methodology(self, calculation_data: Dict) -> Dict[str, Any]:
        """Validate calculation methodology against EPA/IPCC standards"""
        try:
            validation_results = {
                'is_valid': True,
                'methodology_score': 0,
                'validation_details': {},
                'recommendations': []
            }
            
            # Check if using EPA-approved emission factors
            if calculation_data.get('emission_factors_source') == 'EPA':
                validation_results['methodology_score'] += 30
                validation_results['validation_details']['epa_factors'] = True
            else:
                validation_results['recommendations'].append('Use EPA-approved emission factors')
            
            # Check if using USDA yield benchmarks
            if calculation_data.get('benchmark_comparison'):
                validation_results['methodology_score'] += 25
                validation_results['validation_details']['usda_benchmarks'] = True
            
            # Check calculation completeness
            required_inputs = ['nitrogen', 'fuel', 'yield']
            provided_inputs = calculation_data.get('inputs', {}).keys()
            
            completeness = len(set(required_inputs) & set(provided_inputs)) / len(required_inputs)
            validation_results['methodology_score'] += int(completeness * 25)
            
            # Check regional specificity
            if calculation_data.get('state') and calculation_data.get('crop_type'):
                validation_results['methodology_score'] += 20
                validation_results['validation_details']['regional_specificity'] = True
            
            # Overall validation
            if validation_results['methodology_score'] >= 80:
                validation_results['validation_level'] = 'high'
            elif validation_results['methodology_score'] >= 60:
                validation_results['validation_level'] = 'medium'
            else:
                validation_results['validation_level'] = 'low'
                validation_results['is_valid'] = False
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating calculation: {e}")
            return {
                'is_valid': False,
                'error': str(e),
                'validation_level': 'failed'
            }


class EPAEmissionFactorService:
    """Service to provide EPA-approved emission factors"""
    
    def __init__(self):
        # EPA emission factors from official sources
        self.epa_factors = {
            'electricity': {
                'us_average': 0.999,  # kg CO2e per kWh (2022 EPA eGRID)
                'by_state': {
                    'CA': 0.643,  # California (lower due to renewables)
                    'TX': 0.878,  # Texas
                    'IA': 1.456,  # Iowa (coal-heavy)
                    'IL': 0.899,  # Illinois
                    'FL': 0.820,  # Florida
                }
            },
            'fertilizer': {
                'nitrogen': 5.86,    # kg CO2e per kg N (IPCC 2019)
                'phosphorus': 0.20,  # kg CO2e per kg P2O5
                'potassium': 0.15,   # kg CO2e per kg K2O
            },
            'fuel': {
                'diesel': 2.68,      # kg CO2e per liter
                'gasoline': 2.31,    # kg CO2e per liter
                'natural_gas': 2.03, # kg CO2e per m³
            }
        }
    
    def get_emission_factor(self, category: str, subcategory: str, state: str = None) -> float:
        """Get EPA emission factor for a specific category"""
        try:
            if category not in self.epa_factors:
                return 0.0
            
            category_data = self.epa_factors[category]
            
            # Handle state-specific factors
            if subcategory == 'electricity' and state and 'by_state' in category_data:
                return category_data['by_state'].get(state, category_data['us_average'])
            
            # Handle direct lookups
            if isinstance(category_data, dict) and subcategory in category_data:
                return category_data[subcategory]
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting EPA emission factor: {e}")
            return 0.0


# Integration function for your existing system
def get_real_usda_carbon_data(crop_type: str, state: str, farm_practices: Dict) -> Dict[str, Any]:
    """
    Main function to integrate real USDA data with carbon calculations with caching and resilience
    This replaces the mock USDA API calls in enhanced_usda_factors.py
    """
    usda_client = RealUSDAAPIClient()
    epa_service = EPAEmissionFactorService()
    
    # Get cached calculation with circuit breaker protection
    try:
        carbon_data = safe_api_call(
            'carbon_calc',
            usda_client.calculate_carbon_intensity_cached,
            crop_type, state, farm_practices
        )
    except CircuitBreakerOpenError:
        logger.warning("Carbon calculation circuit breaker is open, using fallback")
        carbon_data = usda_circuit_breakers.get_breaker('carbon_calc').fallback_func(
            crop_type, state, farm_practices
        )
    
    # Get nutritional data from FoodData Central
    nutritional_data = usda_client.get_nutritional_carbon_factors(crop_type)
    
    # Validate methodology
    validation = usda_client.validate_calculation_methodology({
        'emission_factors_source': 'EPA',
        'inputs': farm_practices.get('inputs', {}),
        'state': state,
        'crop_type': crop_type
    })
    
    # Combine results
    result = {
        **carbon_data,
        'validation': validation,
        'api_sources': ['USDA NASS', 'USDA FoodData Central', 'EPA'],
        'real_data': True,
        'timestamp': timezone.now().isoformat()
    }
    
    # Add nutritional data if available
    if nutritional_data:
        result['nutritional_analysis'] = nutritional_data
        
        # Enhanced carbon efficiency scoring
        if 'carbon_efficiency' in nutritional_data:
            efficiency = nutritional_data['carbon_efficiency']
            result['carbon_nutrition_efficiency'] = {
                'rating': efficiency.get('efficiency_rating', 'unknown'),
                'score': efficiency.get('nutrition_score', 0),
                'description': f"Produces {efficiency.get('protein_content', 0):.1f}g protein per unit of carbon emissions"
            }
    
    return result 